"""
任务提交工具（简化版）
独立的工具函数，用于不支持Celery的轻量级架构

可以通过设置环境变量 USE_SIMPLE_TASK_RUNNER=true 来启用此简化版本
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

USE_SIMPLE_RUNNER = os.getenv('USE_SIMPLE_TASK_RUNNER', 'true').lower() == 'true'

if USE_SIMPLE_RUNNER:
    logger.info("使用简化任务提交器（无Celery依赖）")
    from backend.utils.simple_task_submitter import get_task_submitter

    def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        提交视频流水线任务

        Args:
            project_id: 项目ID
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径

        Returns:
            任务提交结果
        """
        try:
            logger.info(f"提交视频流水线任务（简化模式）: {project_id}")

            submitter = get_task_submitter()
            result = submitter.submit_video_pipeline(
                project_id=project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path
            )

            logger.info(f"视频流水线任务已提交: {result['task_id']}")
            return result

        except Exception as e:
            logger.error(f"提交视频流水线任务失败: {project_id}, 错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '任务提交失败'
            }

    def submit_import_task(project_id: str, video_path: str, srt_file_path: str = None) -> Dict[str, Any]:
        """
        提交导入任务

        Args:
            project_id: 项目ID
            video_path: 视频路径
            srt_file_path: SRT文件路径

        Returns:
            任务提交结果
        """
        try:
            logger.info(f"提交导入任务（简化模式）: {project_id}")

            submitter = get_task_submitter()
            result = submitter.submit_import_task(
                project_id=project_id,
                video_path=video_path,
                srt_file_path=srt_file_path
            )

            logger.info(f"导入任务已提交: {result['task_id']}")
            return result

        except Exception as e:
            logger.error(f"提交导入任务失败: {project_id}, 错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '任务提交失败'
            }

    def get_task_state(task_id: str) -> str:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        try:
            submitter = get_task_submitter()
            state = submitter.get_task_state(task_id)
            return state.value
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
            return "UNKNOWN"

    def revoke_task(task_id: str) -> Dict[str, Any]:
        """
        撤销任务

        Args:
            task_id: 任务ID

        Returns:
            撤销结果
        """
        try:
            submitter = get_task_submitter()
            submitter.revoke_task(task_id)
            return {'success': True, 'task_id': task_id}
        except Exception as e:
            logger.error(f"撤销任务失败: {task_id}, 错误: {e}")
            return {'success': False, 'error': str(e)}

else:
    logger.info("使用Celery任务提交器")
    from backend.core.celery_app import celery_app

    def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        提交视频流水线任务（Celery模式）

        Args:
            project_id: 项目ID
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径

        Returns:
            任务提交结果
        """
        try:
            logger.info(f"提交视频流水线任务（Celery模式）: {project_id}")

            celery_task = celery_app.send_task(
                'backend.tasks.processing.process_video_pipeline',
                args=[project_id, input_video_path, input_srt_path]
            )

            logger.info(f"视频流水线任务已提交: {celery_task.id}")
            return {
                'success': True,
                'task_id': celery_task.id,
                'status': 'PENDING',
                'message': '视频流水线任务已提交'
            }

        except Exception as e:
            logger.error(f"提交视频流水线任务失败: {project_id}, 错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '任务提交失败'
            }

    def submit_import_task(project_id: str, video_path: str, srt_file_path: str = None) -> Dict[str, Any]:
        """
        提交导入任务（Celery模式）

        Args:
            project_id: 项目ID
            video_path: 视频路径
            srt_file_path: SRT文件路径

        Returns:
            任务提交结果
        """
        try:
            logger.info(f"提交导入任务（Celery模式）: {project_id}")

            celery_task = celery_app.send_task(
                'backend.tasks.import_processing.process_import_task',
                args=[project_id, video_path, srt_file_path]
            )

            logger.info(f"导入任务已提交: {celery_task.id}")
            return {
                'success': True,
                'task_id': celery_task.id,
                'status': 'PENDING',
                'message': '导入任务已提交'
            }

        except Exception as e:
            logger.error(f"提交导入任务失败: {project_id}, 错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '任务提交失败'
            }

    def get_task_state(task_id: str) -> str:
        """
        获取任务状态（Celery模式）

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        try:
            from celery.result import AsyncResult
            result = AsyncResult(task_id, app=celery_app)
            return result.state
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
            return "UNKNOWN"

    def revoke_task(task_id: str) -> Dict[str, Any]:
        """
        撤销任务（Celery模式）

        Args:
            task_id: 任务ID

        Returns:
            撤销结果
        """
        try:
            from celery.result import AsyncResult
            result = AsyncResult(task_id, app=celery_app)
            result.revoke(terminate=True)
            return {'success': True, 'task_id': task_id}
        except Exception as e:
            logger.error(f"撤销任务失败: {task_id}, 错误: {e}")
            return {'success': False, 'error': str(e)}
