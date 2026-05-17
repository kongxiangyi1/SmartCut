"""
异步任务管理器
安全管理异步任务的创建和执行
"""

import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class TaskManager:
    """异步任务管理器"""

    def __init__(self):
        self.tasks = {}

    async def create_safe_task(self, task_name: str, func: Callable, *args, **kwargs) -> asyncio.Task:
        """创建安全的异步任务"""
        logger.info(f"创建异步任务: {task_name}")
        
        async def wrapper():
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"任务 {task_name} 执行失败: {e}")
                raise
        
        task = asyncio.create_task(wrapper())
        self.tasks[task_name] = task
        
        # 任务完成后自动清理
        def cleanup(task: asyncio.Task):
            del self.tasks[task_name]
        
        task.add_done_callback(cleanup)
        
        return task

    def get_task(self, task_name: str) -> Optional[asyncio.Task]:
        """获取任务"""
        return self.tasks.get(task_name)

    def cancel_task(self, task_name: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_name)
        if task and not task.done():
            task.cancel()
            logger.info(f"任务已取消: {task_name}")
            return True
        return False


# 创建全局任务管理器实例
task_manager = TaskManager()
