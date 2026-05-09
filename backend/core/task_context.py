"""
任务上下文封装
为任务函数提供与Celery兼容的接口
使其可以在LightweightTaskExecutor中运行
"""

import logging
from typing import Dict, Any, Optional, Callable
from threading import Lock

logger = logging.getLogger(__name__)

class TaskContext:
    """
    任务上下文封装类
    模拟Celery的self.update_state()接口
    """

    def __init__(
        self,
        task_id: str,
        task_name: str,
        update_progress_callback: Optional[Callable] = None
    ):
        self.task_id = task_id
        self.task_name = task_name
        self._state = "PENDING"
        self._meta: Dict[str, Any] = {}
        self._progress_callback = update_progress_callback
        self._lock = Lock()

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str):
        self._state = value

    @property
    def meta(self) -> Dict[str, Any]:
        return self._meta

    def update_state(self, state: str = None, meta: Dict[str, Any] = None):
        """
        更新任务状态

        Args:
            state: 任务状态 (PENDING, STARTED, PROGRESS, SUCCESS, FAILURE)
            meta: 状态元数据，包含进度等信息
        """
        with self._lock:
            if state is not None:
                self._state = state
            if meta is not None:
                self._meta.update(meta)

            if self._progress_callback and meta:
                progress = meta.get('progress', 0)
                self._progress_callback(progress, meta)

        logger.debug(f"Task {self.task_id} state updated: {self._state}, meta: {self._meta}")

    def get_progress(self) -> float:
        """获取当前进度"""
        return self._meta.get('progress', 0.0)


class TaskWrapper:
    """
    任务函数包装器
    将普通函数包装成可以在LightweightTaskExecutor中执行的带上下文任务
    """

    def __init__(self, func: Callable, task_name: str):
        self.func = func
        self.task_name = task_name

    def __call__(self, *args, task_id: str = None, progress_callback: Callable = None, **kwargs):
        """
        执行任务

        Args:
            *args: 位置参数
            task_id: 任务ID
            progress_callback: 进度回调函数
            **kwargs: 关键字参数
        """
        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        context = TaskContext(task_id, self.task_name, progress_callback)

        def wrapped_func():
            context.update_state(state='STARTED', meta={'progress': 0, 'message': '任务开始'})

            try:
                result = self.func(context, *args, **kwargs)
                context.update_state(state='SUCCESS', meta={'progress': 100, 'message': '任务完成'})
                return result
            except Exception as e:
                context.update_state(state='FAILURE', meta={'error': str(e)})
                raise

        return wrapped_func


def create_task_wrapper(func: Callable, task_name: str = None) -> TaskWrapper:
    """
    为任务函数创建包装器

    Args:
        func: 任务函数，第一个参数应该是context
        task_name: 任务名称

    Returns:
        TaskWrapper: 任务包装器
    """
    if task_name is None:
        task_name = func.__name__
    return TaskWrapper(func, task_name)
