"""
轻量级任务执行器
替代Celery + Redis，用于桌面应用的简化架构
"""

import os
import sys
import logging
import traceback
import uuid
import signal
import atexit
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, Future
from threading import Lock
from queue import Queue, Empty
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import multiprocessing

logger = logging.getLogger(__name__)

class TaskState(Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"

@dataclass
class TaskResult:
    task_id: str
    state: TaskState
    result: Any = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class LightweightTaskExecutor:
    """
    轻量级任务执行器
    使用ProcessPoolExecutor实现多进程并行处理
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._executor: Optional[ProcessPoolExecutor] = None
        self._futures: Dict[str, Future] = {}
        self._results: Dict[str, TaskResult] = {}
        self._progress_callbacks: Dict[str, Callable] = {}
        self._max_workers = max(1, multiprocessing.cpu_count() - 1)

        atexit.register(self.shutdown)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"LightweightTaskExecutor initialized with {self._max_workers} workers")

    def _signal_handler(self, signum, frame):
        logger.info("Received shutdown signal")
        self.shutdown()
        sys.exit(0)

    @property
    def executor(self) -> ProcessPoolExecutor:
        if self._executor is None or self._executor._shutdown:
            self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        return self._executor

    def submit(
        self,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        提交任务

        Args:
            func: 要执行的函数
            *args: 位置参数
            task_id: 任务ID，不提供则自动生成
            progress_callback: 进度回调函数
            **kwargs: 关键字参数

        Returns:
            task_id: 任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        result = TaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        if progress_callback:
            self._progress_callbacks[task_id] = progress_callback

        def wrapped_func():
            result.started_at = datetime.now()
            result.state = TaskState.STARTED
            try:
                logger.info(f"Task {task_id} started")
                output = func(*args, **kwargs)
                result.state = TaskState.SUCCESS
                result.result = output
                result.completed_at = datetime.now()
                logger.info(f"Task {task_id} completed successfully")
                return output
            except Exception as e:
                result.state = TaskState.FAILURE
                result.error = str(e)
                result.traceback = traceback.format_exc()
                result.completed_at = datetime.now()
                logger.error(f"Task {task_id} failed: {e}")
                raise

        future = self.executor.submit(wrapped_func)
        self._futures[task_id] = future

        return task_id

    def submit_thread(
        self,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        提交线程任务（用于I/O密集型任务）

        Args:
            func: 要执行的函数
            *args: 位置参数
            task_id: 任务ID，不提供则自动生成
            progress_callback: 进度回调函数
            **kwargs: 关键字参数

        Returns:
            task_id: 任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        result = TaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        if progress_callback:
            self._progress_callbacks[task_id] = progress_callback

        def wrapped_func():
            result.started_at = datetime.now()
            result.state = TaskState.STARTED
            try:
                logger.info(f"Thread task {task_id} started")
                output = func(*args, **kwargs)
                result.state = TaskState.SUCCESS
                result.result = output
                result.completed_at = datetime.now()
                logger.info(f"Thread task {task_id} completed successfully")
                return output
            except Exception as e:
                result.state = TaskState.FAILURE
                result.error = str(e)
                result.traceback = traceback.format_exc()
                result.completed_at = datetime.now()
                logger.error(f"Thread task {task_id} failed: {e}")
                raise

        with ThreadPoolExecutor(max_workers=self._max_workers * 2) as thread_executor:
            future = thread_executor.submit(wrapped_func)
            self._futures[task_id] = future

        return task_id

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        return self._results.get(task_id)

    def get_state(self, task_id: str) -> TaskState:
        """获取任务状态"""
        if task_id not in self._results:
            return TaskState.PENDING

        result = self._results[task_id]
        future = self._futures.get(task_id)

        if future is None:
            return result.state

        if future.done():
            if result.state != TaskState.FAILURE:
                result.state = TaskState.SUCCESS
            return result.state

        if result.state == TaskState.PENDING and future.running():
            result.state = TaskState.STARTED

        return result.state

    def update_progress(self, task_id: str, progress: float, metadata: Dict[str, Any] = None):
        """更新任务进度"""
        if task_id in self._results:
            self._results[task_id].progress = progress
            if metadata:
                self._results[task_id].metadata.update(metadata)
            self._results[task_id].state = TaskState.PROGRESS

            if task_id in self._progress_callbacks:
                try:
                    self._progress_callbacks[task_id](progress, metadata)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

    def revoke(self, task_id: str, terminate: bool = False):
        """撤销任务"""
        if task_id in self._futures:
            future = self._futures[task_id]
            if not future.done():
                future.cancel()
                if terminate:
                    logger.warning(f"Task {task_id} termination requested (force cancel)")
            self._results[task_id].state = TaskState.REVOKED

    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        logger.info("Shutting down LightweightTaskExecutor")
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def get_active_count(self) -> int:
        """获取活跃任务数"""
        return sum(1 for f in self._futures.values() if not f.done())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._results)
        completed = sum(1 for r in self._results.values() if r.state == TaskState.SUCCESS)
        failed = sum(1 for r in self._results.values() if r.state == TaskState.FAILURE)
        running = self.get_active_count()

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "max_workers": self._max_workers,
        }


task_executor = LightweightTaskExecutor()

def get_task_executor() -> LightweightTaskExecutor:
    """获取任务执行器单例"""
    return task_executor
