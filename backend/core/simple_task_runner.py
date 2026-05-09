"""
简化的任务运行器
替代Celery，用于桌面应用的轻量级任务处理
"""

import os
import sys
import logging
import traceback
import uuid
import threading
import multiprocessing
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import queue

logger = logging.getLogger(__name__)

class TaskState(Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"

@dataclass
class SimpleTaskResult:
    task_id: str
    state: TaskState
    result: Any = None
    error: Optional[str] = None
    traceback_str: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class SimpleTaskContext:
    """简化的任务上下文，模拟Celery的self对象"""

    def __init__(self, task_id: str, task_name: str, update_callback: Optional[Callable] = None):
        self.request = type('obj', (object,), {'id': task_id})()
        self.task_id = task_id
        self.task_name = task_name
        self._state = TaskState.PENDING
        self._meta: Dict[str, Any] = {}
        self._update_callback = update_callback
        self._lock = threading.Lock()

    @property
    def state(self):
        return self._state

    def update_state(self, state: str = None, meta: Dict[str, Any] = None):
        """更新任务状态，兼容Celery接口"""
        with self._lock:
            if state is not None:
                self._state = TaskState(state)
            if meta is not None:
                self._meta.update(meta)

            if self._update_callback:
                progress = meta.get('progress', 0) if meta else 0
                self._update_callback(self.task_id, progress, self._meta)

    def update_progress(self, progress: float, message: str = ""):
        """更新进度"""
        with self._lock:
            self._state = TaskState.PROGRESS
            self._meta['progress'] = progress
            if message:
                self._meta['message'] = message

            if self._update_callback:
                self._update_callback(self.task_id, progress, self._meta)

class SimpleTaskRunner:
    """
    简化的任务运行器
    使用线程池处理任务，支持进度更新
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._process_pool: Optional[ProcessPoolExecutor] = None
        self._tasks: Dict[str, SimpleTaskContext] = {}
        self._results: Dict[str, SimpleTaskResult] = {}
        self._progress_callback: Optional[Callable] = None
        self._max_workers = max(1, multiprocessing.cpu_count() - 1)
        self._lock = threading.Lock()

        logger.info(f"SimpleTaskRunner initialized with {self._max_workers} workers")

    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self._progress_callback = callback

    def _default_progress_callback(self, task_id: str, progress: float, meta: Dict[str, Any]):
        """默认进度回调"""
        logger.info(f"Task {task_id}: {progress}% - {meta.get('message', '')}")

    def submit(
        self,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        task_name: str = "unknown",
        use_process: bool = False,
        **kwargs
    ) -> str:
        """
        提交任务

        Args:
            func: 任务函数
            *args: 位置参数
            task_id: 任务ID
            task_name: 任务名称（用于日志）
            use_process: 是否使用进程池（CPU密集型任务）
            **kwargs: 关键字参数

        Returns:
            task_id: 任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        context = SimpleTaskContext(
            task_id,
            task_name,
            self._progress_callback or self._default_progress_callback
        )

        result = SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)
        with self._lock:
            self._tasks[task_id] = context
            self._results[task_id] = result

        def run_task():
            context._state = TaskState.STARTED
            result.state = TaskState.STARTED
            result.started_at = datetime.now()

            logger.info(f"Task {task_id} ({task_name}) started")

            try:
                task_func = func.__get__(context, SimpleTaskContext)
                output = task_func(*args, **kwargs)

                result.state = TaskState.SUCCESS
                result.result = output
                result.progress = 100
                logger.info(f"Task {task_id} ({task_name}) completed successfully")

            except Exception as e:
                result.state = TaskState.FAILURE
                result.error = str(e)
                result.traceback_str = traceback.format_exc()
                logger.error(f"Task {task_id} ({task_name}) failed: {e}\n{traceback.format_exc()}")

            finally:
                result.completed_at = datetime.now()

        if use_process:
            if self._process_pool is None:
                self._process_pool = ProcessPoolExecutor(max_workers=self._max_workers)
            self._process_pool.submit(run_task)
        else:
            if self._thread_pool is None:
                self._thread_pool = ThreadPoolExecutor(max_workers=self._max_workers * 2)
            self._thread_pool.submit(run_task)

        return task_id

    def get_result(self, task_id: str) -> Optional[SimpleTaskResult]:
        """获取任务结果"""
        return self._results.get(task_id)

    def get_state(self, task_id: str) -> TaskState:
        """获取任务状态"""
        if task_id not in self._results:
            return TaskState.PENDING
        return self._results[task_id].state

    def get_progress(self, task_id: str) -> float:
        """获取任务进度"""
        if task_id in self._tasks:
            return self._tasks[task_id]._meta.get('progress', 0.0)
        return 0.0

    def revoke(self, task_id: str):
        """取消任务（标记，不实际停止正在运行的任务）"""
        if task_id in self._results:
            self._results[task_id].state = TaskState.CANCELLED
            logger.info(f"Task {task_id} marked as cancelled")

    def shutdown(self, wait: bool = True):
        """关闭任务运行器"""
        logger.info("Shutting down SimpleTaskRunner")

        if self._thread_pool:
            self._thread_pool.shutdown(wait=wait)
            self._thread_pool = None

        if self._process_pool:
            self._process_pool.shutdown(wait=wait)
            self._process_pool = None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._results)
            completed = sum(1 for r in self._results.values() if r.state == TaskState.SUCCESS)
            failed = sum(1 for r in self._results.values() if r.state == TaskState.FAILURE)
            running = sum(1 for r in self._results.values() if r.state in (TaskState.STARTED, TaskState.PROGRESS))

            return {
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "max_workers": self._max_workers,
            }


task_runner = SimpleTaskRunner()

def get_task_runner() -> SimpleTaskRunner:
    """获取任务运行器单例"""
    return task_runner
