"""
简化任务提交器
支持细粒度进度反馈和WebSocket推送
"""

import logging
import os
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass
class SimpleTaskResult:
    """任务结果"""
    task_id: str
    state: TaskState = TaskState.PENDING
    progress: float = 0.0
    result: Any = None
    error: str = None
    traceback_str: str = None
    started_at: datetime = None
    completed_at: datetime = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimpleTaskContext:
    """任务上下文"""
    task_id: str
    task_name: str
    progress_callback: Optional[Callable] = None
    _state: TaskState = TaskState.PENDING
    _progress: float = 0.0
    _metadata: Dict[str, Any] = field(default_factory=dict)

    def update_progress(self, progress: float, message: str = None, **kwargs):
        """更新进度"""
        self._progress = progress
        if message or kwargs:
            self._metadata['message'] = message or ''
            self._metadata.update(kwargs)

        if self.progress_callback:
            self.progress_callback(self.task_id, progress, self._metadata)

    def get_progress(self) -> float:
        """获取当前进度"""
        return self._progress

    def get_state(self) -> TaskState:
        """获取当前状态"""
        return self._state


class SimplifiedTaskSubmitter:
    """
    增强的任务提交器
    支持细粒度进度反馈和WebSocket推送
    """

    _instance = None
    _lock = threading.Lock()

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
        max_workers = int(os.environ.get("MAX_WORKERS", "4"))
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, SimpleTaskContext] = {}
        self._results: Dict[str, SimpleTaskResult] = {}
        self._websocket_notifier = None

        logger.info(f"[TaskSubmitter] 初始化完成，最大并发数: {max_workers}")

    def set_websocket_notifier(self, notifier):
        """设置WebSocket通知器"""
        self._websocket_notifier = notifier
        logger.info("[TaskSubmitter] WebSocket通知器已设置")

    def _create_task_context(
        self,
        task_id: str,
        task_name: str,
        project_id: str = None,
        progress_callback: Callable = None
    ) -> SimpleTaskContext:
        """创建任务上下文"""
        if progress_callback is None:
            progress_callback = self._default_progress_callback

        def wrapped_callback(tid: str, progress: float, meta: Dict[str, Any]):
            progress_callback(tid, progress, meta)
            if self._websocket_notifier and project_id:
                try:
                    self._websocket_notifier.notify_progress(
                        project_id=project_id,
                        progress=progress,
                        stage=meta.get('stage'),
                        message=meta.get('message')
                    )
                except Exception as e:
                    logger.warning(f"[TaskSubmitter] WebSocket推送失败: {e}")

        return SimpleTaskContext(task_id, task_name, wrapped_callback)

    def _default_progress_callback(self, task_id: str, progress: float, meta: Dict[str, Any]):
        """默认进度回调"""
        logger.info(f"[TaskSubmitter] Task {task_id}: {progress:.1f}% - {meta.get('message', '')}")

        task_result = self._results.get(task_id)
        if task_result:
            task_result.progress = progress
            task_result.metadata = meta

    def submit_video_pipeline(
        self,
        project_id: str,
        input_video_path: str,
        input_srt_path: str = None,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        提交视频流水线任务（立即返回）

        Args:
            project_id: 项目ID
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            task_id: 任务ID

        Returns:
            任务提交结果（立即返回）
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        logger.info(f"[TaskSubmitter] 提交视频流水线任务: {project_id}, task_id: {task_id}")

        context = self._create_task_context(task_id, "process_video_pipeline", project_id)
        self._tasks[task_id] = context

        result = SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        self._executor.submit(
            self._run_video_pipeline_task,
            task_id, project_id, input_video_path, input_srt_path, context, result
        )

        return {
            'success': True,
            'task_id': task_id,
            'project_id': project_id,
            'status': 'PENDING',
            'message': '视频流水线任务已提交，正在后台处理'
        }

    def _run_video_pipeline_task(
        self,
        task_id: str,
        project_id: str,
        input_video_path: str,
        input_srt_path: str,
        context: SimpleTaskContext,
        result: SimpleTaskResult
    ):
        """执行视频流水线任务（后台线程）"""
        context._state = TaskState.STARTED
        result.state = TaskState.STARTED
        result.started_at = datetime.now()

        db = None
        try:
            db = self._get_db_session()

            context.update_progress(5, "初始化任务...")

            context.update_progress(10, "执行流水线处理...")

            import asyncio
            from backend.services.simple_pipeline_adapter import create_simple_pipeline_adapter

            pipeline_adapter = create_simple_pipeline_adapter(str(project_id), str(task_id))

            pipeline_result = asyncio.run(
                pipeline_adapter.process_project_sync(input_video_path, input_srt_path)
            )

            context.update_progress(90, "处理完成...")

            if pipeline_result.get("status") == "failed":
                error_msg = pipeline_result.get("message", "处理失败")
                result.state = TaskState.FAILURE
                result.error = error_msg
                context._state = TaskState.FAILURE

                logger.error(f"[TaskSubmitter] 视频处理失败: {project_id}, error: {error_msg}")
            else:
                result.state = TaskState.SUCCESS
                result.result = pipeline_result
                result.progress = 100
                context._state = TaskState.SUCCESS

                logger.info(f"[TaskSubmitter] 视频处理成功: {project_id}")

            if self._websocket_notifier:
                try:
                    self._websocket_notifier.notify_completion(
                        project_id=project_id,
                        success=result.state == TaskState.SUCCESS,
                        error=result.error
                    )
                except Exception as e:
                    logger.warning(f"[TaskSubmitter] WebSocket推送失败: {e}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TaskSubmitter] 视频处理异常: {project_id}, error: {error_msg}\n{traceback.format_exc()}")

            result.state = TaskState.FAILURE
            result.error = error_msg
            result.traceback_str = traceback.format_exc()
            context._state = TaskState.FAILURE

            if self._websocket_notifier:
                try:
                    self._websocket_notifier.notify_completion(
                        project_id=project_id,
                        success=False,
                        error=error_msg
                    )
                except Exception as e:
                    logger.warning(f"[TaskSubmitter] WebSocket推送失败: {e}")

        finally:
            result.completed_at = datetime.now()
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def submit_import_task(
        self,
        project_id: str,
        video_path: str,
        srt_file_path: str = None,
        task_id: str = None
    ) -> Dict[str, Any]:
        """提交导入任务"""
        if task_id is None:
            task_id = str(uuid.uuid4())

        logger.info(f"[TaskSubmitter] 提交导入任务: {project_id}, task_id: {task_id}")

        context = self._create_task_context(task_id, "process_import", project_id)
        self._tasks[task_id] = context

        result = SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        self._executor.submit(
            self._run_import_task,
            task_id, project_id, video_path, srt_file_path, context, result
        )

        return {
            'success': True,
            'task_id': task_id,
            'project_id': project_id,
            'status': 'PENDING',
            'message': '导入任务已提交，正在后台处理'
        }

    def _run_import_task(
        self,
        task_id: str,
        project_id: str,
        video_path: str,
        srt_file_path: str,
        context: SimpleTaskContext,
        result: SimpleTaskResult
    ):
        """执行导入任务 - 调用视频流水线处理"""
        context._state = TaskState.STARTED
        result.state = TaskState.STARTED
        result.started_at = datetime.now()

        try:
            context.update_progress(10, "开始导入...")

            # 调用视频流水线处理任务
            self._run_video_pipeline_task(task_id, project_id, video_path, srt_file_path, context, result)

            if self._websocket_notifier:
                try:
                    self._websocket_notifier.notify_completion(
                        project_id=project_id,
                        success=True
                    )
                except Exception as e:
                    logger.warning(f"[TaskSubmitter] WebSocket推送失败: {e}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TaskSubmitter] 导入任务失败: {project_id}, error: {error_msg}")

            result.state = TaskState.FAILURE
            result.error = error_msg
            result.traceback_str = traceback.format_exc()
            context._state = TaskState.FAILURE

            if self._websocket_notifier:
                try:
                    self._websocket_notifier.notify_completion(
                        project_id=project_id,
                        success=False,
                        error=error_msg
                    )
                except Exception as e:
                    logger.warning(f"[TaskSubmitter] WebSocket推送失败: {e}")

        finally:
            result.completed_at = datetime.now()

    def get_task_state(self, task_id: str) -> TaskState:
        """获取任务状态"""
        if task_id in self._results:
            return self._results[task_id].state
        return TaskState.PENDING

    def get_task_result(self, task_id: str) -> Optional[SimpleTaskResult]:
        """获取任务结果"""
        return self._results.get(task_id)

    def revoke_task(self, task_id: str):
        """撤销任务"""
        logger.info(f"[TaskSubmitter] 撤销任务: {task_id}")
        if task_id in self._tasks:
            self._tasks[task_id]._state = TaskState.FAILURE
            self._tasks[task_id]._metadata['message'] = '任务被撤销'
        if task_id in self._results:
            self._results[task_id].state = TaskState.FAILURE
            self._results[task_id].error = '任务被撤销'

    def _get_db_session(self):
        """获取数据库会话"""
        try:
            from backend.core.database import SessionLocal
            return SessionLocal()
        except Exception as e:
            logger.warning(f"[TaskSubmitter] 无法获取数据库会话: {e}")
            return None


def get_task_submitter() -> SimplifiedTaskSubmitter:
    """获取任务提交器单例"""
    return SimplifiedTaskSubmitter()
