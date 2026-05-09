"""
简化的任务提交工具
替代Celery的任务提交，用于桌面应用的轻量级架构
"""

import logging
import traceback
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing

from backend.core.simple_task_runner import get_task_runner, SimpleTaskContext, SimpleTaskResult, TaskState
from backend.core.database import SessionLocal
from backend.models.task import Task, TaskStatus, TaskType
from backend.models.project import Project, ProjectStatus
from datetime import datetime

logger = logging.getLogger(__name__)

class SimplifiedTaskSubmitter:
    """
    简化的任务提交器
    直接调用任务函数，使用线程池执行
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
        self._executor = ThreadPoolExecutor(max_workers=max(1, multiprocessing.cpu_count() - 1))
        self._tasks: Dict[str, SimpleTaskContext] = {}
        self._results: Dict[str, SimpleTaskResult] = {}

    def _create_task_context(self, task_id: str, task_name: str):
        """创建任务上下文"""
        def progress_callback(task_id: str, progress: float, meta: Dict[str, Any]):
            logger.info(f"Task {task_id}: {progress}% - {meta.get('message', '')}")

            task_result = self._results.get(task_id)
            if task_result:
                task_result.progress = progress
                task_result.metadata = meta

            try:
                db = SessionLocal()
                task = db.query(Task).filter(Task.celery_task_id == task_id).first()
                if task:
                    task.progress = progress
                    task.current_step = meta.get('message', task.current_step)
                    db.commit()
            except Exception as e:
                logger.warning(f"Failed to update task progress: {e}")
            finally:
                db.close()

        return SimpleTaskContext(task_id, task_name, progress_callback)

    def submit_video_pipeline(
        self,
        project_id: str,
        input_video_path: str,
        input_srt_path: str = None,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        提交视频流水线任务

        Args:
            project_id: 项目ID
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            task_id: 任务ID

        Returns:
            任务提交结果
        """
        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        logger.info(f"提交视频流水线任务: {project_id}, task_id: {task_id}")

        context = self._create_task_context(task_id, "process_video_pipeline")
        self._tasks[task_id] = context

        result = SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        def run_task():
            context._state = TaskState.STARTED
            result.state = TaskState.STARTED
            result.started_at = datetime.now()

            db = None
            try:
                db = SessionLocal()

                task = Task(
                    name="视频处理流水线",
                    description=f"处理项目 {project_id} 的完整视频流水线",
                    task_type=TaskType.VIDEO_PROCESSING,
                    project_id=project_id,
                    celery_task_id=task_id,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    current_step="初始化",
                    total_steps=6
                )
                db.add(task)

                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.status = ProjectStatus.PROCESSING
                    project.updated_at = datetime.utcnow()

                db.commit()
                logger.info(f"任务记录已创建: {task.id}")

                context.update_progress(5, "开始处理...")

                from backend.services.simple_pipeline_adapter import create_simple_pipeline_adapter
                pipeline_adapter = create_simple_pipeline_adapter(str(project_id), str(task.id))

                context.update_progress(10, "执行流水线处理...")

                import asyncio
                pipeline_result = asyncio.run(
                    pipeline_adapter.process_project_sync(input_video_path, input_srt_path)
                )

                context.update_progress(90, "处理完成...")

                if pipeline_result.get("status") == "failed":
                    error_msg = pipeline_result.get("message", "处理失败")
                    task.status = TaskStatus.FAILED
                    task.error_message = error_msg
                    task.result_data = pipeline_result

                    if project:
                        project.status = ProjectStatus.FAILED
                        project.updated_at = datetime.utcnow()

                    db.commit()

                    result.state = TaskState.FAILURE
                    result.error = error_msg
                    context._state = TaskState.FAILURE

                    logger.error(f"视频处理失败: {project_id}, error: {error_msg}")

                    return {
                        "success": False,
                        "project_id": project_id,
                        "task_id": task_id,
                        "error": error_msg,
                        "result": pipeline_result
                    }
                else:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.current_step = "处理完成"
                    task.result_data = pipeline_result

                    if project:
                        project.status = ProjectStatus.COMPLETED
                        project.completed_at = datetime.utcnow()

                    db.commit()

                    result.state = TaskState.SUCCESS
                    result.result = pipeline_result
                    result.progress = 100
                    context._state = TaskState.SUCCESS

                    logger.info(f"视频处理成功: {project_id}")

                    return {
                        "success": True,
                        "project_id": project_id,
                        "task_id": task_id,
                        "result": pipeline_result
                    }

            except Exception as e:
                error_msg = str(e)
                logger.error(f"视频处理异常: {project_id}, error: {error_msg}\n{traceback.format_exc()}")

                if db:
                    try:
                        task = db.query(Task).filter(Task.celery_task_id == task_id).first()
                        if task:
                            task.status = TaskStatus.FAILED
                            task.error_message = error_msg

                        project = db.query(Project).filter(Project.id == project_id).first()
                        if project:
                            project.status = ProjectStatus.FAILED
                            project.updated_at = datetime.utcnow()

                        db.commit()
                    except Exception as update_error:
                        logger.error(f"Failed to update task status: {update_error}")

                result.state = TaskState.FAILURE
                result.error = error_msg
                result.traceback_str = traceback.format_exc()
                context._state = TaskState.FAILURE

                return {
                    "success": False,
                    "project_id": project_id,
                    "task_id": task_id,
                    "error": error_msg
                }

            finally:
                result.completed_at = datetime.now()
                if db:
                    db.close()

        self._executor.submit(run_task)

        return {
            'success': True,
            'task_id': task_id,
            'status': 'PENDING',
            'message': '视频流水线任务已提交'
        }

    def submit_import_task(
        self,
        project_id: str,
        video_path: str,
        srt_file_path: str = None,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        提交导入任务

        Args:
            project_id: 项目ID
            video_path: 视频路径
            srt_file_path: SRT文件路径
            task_id: 任务ID

        Returns:
            任务提交结果
        """
        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        logger.info(f"提交导入任务: {project_id}, task_id: {task_id}")

        context = self._create_task_context(task_id, "process_import_task")
        self._tasks[task_id] = context

        result = SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)
        self._results[task_id] = result

        def run_task():
            context._state = TaskState.STARTED
            result.state = TaskState.STARTED
            result.started_at = datetime.now()

            db = None
            try:
                db = SessionLocal()
                from backend.services.project_service import ProjectService

                context.update_progress(10, "开始处理...")

                project_service = ProjectService(db)
                project = project_service.get(project_id)

                if not project:
                    raise ValueError(f"项目不存在: {project_id}")

                context.update_progress(20, "检查缩略图...")

                from backend.utils.thumbnail_generator import generate_project_thumbnail
                from pathlib import Path

                if not project.thumbnail:
                    context.update_progress(25, "生成缩略图...")
                    thumbnail_data = generate_project_thumbnail(project_id, Path(video_path))
                    if thumbnail_data:
                        project.thumbnail = thumbnail_data
                        db.commit()

                context.update_progress(40, "提交视频处理任务...")

                submit_result = self.submit_video_pipeline(
                    project_id=project_id,
                    input_video_path=video_path,
                    input_srt_path=srt_file_path
                )

                context.update_progress(100, "导入任务完成")
                result.state = TaskState.SUCCESS
                result.result = submit_result
                context._state = TaskState.SUCCESS

                return submit_result

            except Exception as e:
                error_msg = str(e)
                logger.error(f"导入任务异常: {project_id}, error: {error_msg}\n{traceback.format_exc()}")

                result.state = TaskState.FAILURE
                result.error = error_msg
                result.traceback_str = traceback.format_exc()
                context._state = TaskState.FAILURE

                return {
                    "success": False,
                    "project_id": project_id,
                    "task_id": task_id,
                    "error": error_msg
                }

            finally:
                result.completed_at = datetime.now()
                if db:
                    db.close()

        self._executor.submit(run_task)

        return {
            'success': True,
            'task_id': task_id,
            'status': 'PENDING',
            'message': '导入任务已提交'
        }

    def get_task_state(self, task_id: str) -> TaskState:
        """获取任务状态"""
        return self._results.get(task_id, SimpleTaskResult(task_id=task_id, state=TaskState.PENDING)).state

    def get_task_result(self, task_id: str) -> Optional[SimpleTaskResult]:
        """获取任务结果"""
        return self._results.get(task_id)

    def revoke_task(self, task_id: str):
        """撤销任务"""
        if task_id in self._results:
            self._results[task_id].state = TaskState.CANCELLED
            logger.info(f"任务已撤销: {task_id}")

    def shutdown(self):
        """关闭任务提交器"""
        self._executor.shutdown(wait=True)


task_submitter = SimplifiedTaskSubmitter()

def get_task_submitter() -> SimplifiedTaskSubmitter:
    """获取任务提交器单例"""
    return task_submitter
