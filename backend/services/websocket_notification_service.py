"""
WebSocket通知服务
用于推送任务进度和完成通知
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class WebSocketNotificationService:
    """WebSocket通知服务"""

    def __init__(self):
        self._gateway = None
        self._enabled = os.environ.get("WEBSOCKET_ENABLED", "true").lower() == "true"
        self._init_gateway()

    def _init_gateway(self):
        """初始化WebSocket网关"""
        if not self._enabled:
            logger.info("[WebSocket] WebSocket通知服务已禁用")
            return

        try:
            from backend.services.websocket_gateway_service import websocket_gateway_service
            self._gateway = websocket_gateway_service
            logger.info("[WebSocket] WebSocket网关连接成功")
        except ImportError:
            logger.warning("[WebSocket] WebSocket网关服务不存在，将使用日志通知")
            self._gateway = None
        except Exception as e:
            logger.warning(f"[WebSocket] WebSocket网关初始化失败: {e}")
            self._gateway = None

    def notify_progress(
        self,
        project_id: str,
        progress: float,
        stage: str = None,
        message: str = None
    ):
        """
        推送进度更新

        Args:
            project_id: 项目ID
            progress: 进度百分比 (0-100)
            stage: 当前阶段
            message: 消息
        """
        try:
            payload = {
                "type": "progress_update",
                "project_id": project_id,
                "progress": float(progress),
                "stage": stage,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            if self._gateway:
                self._gateway.broadcast_to_project(project_id, payload)
                logger.debug(f"[WebSocket] 进度推送: {project_id} - {progress}%")
            else:
                logger.info(f"[WebSocket] 进度更新: {project_id} - {progress}% - {message}")

        except Exception as e:
            logger.warning(f"[WebSocket] 进度推送失败: {e}")

    def notify_completion(
        self,
        project_id: str,
        success: bool,
        error: str = None
    ):
        """
        推送完成通知

        Args:
            project_id: 项目ID
            success: 是否成功
            error: 错误信息
        """
        try:
            payload = {
                "type": "task_completion",
                "project_id": project_id,
                "success": success,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            }

            if self._gateway:
                self._gateway.broadcast_to_project(project_id, payload)
                logger.info(
                    f"[WebSocket] 完成通知: {project_id} - "
                    f"{'成功' if success else '失败'}"
                )
            else:
                logger.info(
                    f"[WebSocket] 任务完成: {project_id} - "
                    f"{'成功' if success else '失败'} - {error or ''}"
                )

        except Exception as e:
            logger.warning(f"[WebSocket] 完成通知推送失败: {e}")

    async def send_processing_started(
        self,
        project_id: str,
        message: str = None
    ):
        """
        推送处理开始通知

        Args:
            project_id: 项目ID
            message: 消息
        """
        self.notify_stage_change(
            project_id=project_id,
            stage="processing_started",
            message=message or "开始处理"
        )

    async def send_processing_error(
        self,
        project_id: str,
        error: str,
        step: str = None
    ):
        """
        推送处理错误通知

        Args:
            project_id: 项目ID
            error: 错误信息
            step: 出错步骤
        """
        self.notify_error(
            project_id=project_id,
            error=error,
            details={"step": step} if step else None
        )

    def notify_stage_change(
        self,
        project_id: str,
        stage: str,
        message: str = None
    ):
        """
        推送阶段变更通知

        Args:
            project_id: 项目ID
            stage: 新阶段
            message: 消息
        """
        try:
            payload = {
                "type": "stage_change",
                "project_id": project_id,
                "stage": stage,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            if self._gateway:
                self._gateway.broadcast_to_project(project_id, payload)
                logger.info(f"[WebSocket] 阶段变更: {project_id} - {stage}")
            else:
                logger.info(f"[WebSocket] 阶段变更: {project_id} - {stage} - {message}")

        except Exception as e:
            logger.warning(f"[WebSocket] 阶段变更推送失败: {e}")

    def notify_error(
        self,
        project_id: str,
        error: str,
        details: dict = None
    ):
        """
        推送错误通知

        Args:
            project_id: 项目ID
            error: 错误信息
            details: 错误详情
        """
        try:
            payload = {
                "type": "error",
                "project_id": project_id,
                "error": error,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }

            if self._gateway:
                self._gateway.broadcast_to_project(project_id, payload)
                logger.error(f"[WebSocket] 错误通知: {project_id} - {error}")
            else:
                logger.error(f"[WebSocket] 错误: {project_id} - {error}")

        except Exception as e:
            logger.warning(f"[WebSocket] 错误通知推送失败: {e}")


websocket_notification_service = WebSocketNotificationService()


def get_websocket_notifier() -> WebSocketNotificationService:
    """获取WebSocket通知服务单例"""
    return websocket_notification_service
