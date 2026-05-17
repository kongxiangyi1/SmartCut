"""
WebSocket连接管理器
负责管理WebSocket连接和消息发送
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketMessage:
    """WebSocket消息构建器"""

    @staticmethod
    def create_system_notification(
        notif_type: str,
        title: str,
        description: str,
        severity: str = "info"
    ) -> Dict[str, Any]:
        """创建系统通知消息"""
        return {
            "type": notif_type,
            "title": title,
            "description": description,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def create_error_notification(
        error_type: str,
        title: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建错误通知消息"""
        return {
            "type": "error",
            "error_type": error_type,
            "title": title,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def create_progress_update(
        task_id: str,
        progress: float,
        stage: str = None,
        message: str = None
    ) -> Dict[str, Any]:
        """创建进度更新消息"""
        return {
            "type": "progress_update",
            "task_id": task_id,
            "progress": progress,
            "stage": stage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }


class ConnectionManager:
    """
    WebSocket连接管理器
    管理活跃连接和用户订阅
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        logger.info("[WebSocketManager] 初始化完成")

    async def connect(self, websocket: WebSocket, user_id: str):
        """连接WebSocket"""
        await websocket.accept()
        async with self._lock:
            self.active_connections[user_id] = websocket
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
        logger.info(f"[WebSocketManager] 用户 {user_id} 已连接")

    async def disconnect(self, user_id: str):
        """断开WebSocket连接"""
        async with self._lock:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
            if user_id in self.user_subscriptions:
                del self.user_subscriptions[user_id]
        logger.info(f"[WebSocketManager] 用户 {user_id} 已断开")

    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """发送个人消息"""
        async with self._lock:
            websocket = self.active_connections.get(user_id)

        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"[WebSocketManager] 发送消息失败: {user_id} - {e}")
                return False
        else:
            logger.warning(f"[WebSocketManager] 用户 {user_id} 不在线，无法发送消息")
            return False

    def subscribe_to_topic(self, user_id: str, topic: str):
        """订阅主题"""
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        self.user_subscriptions[user_id].add(topic)
        logger.debug(f"[WebSocketManager] 用户 {user_id} 订阅主题: {topic}")

    def unsubscribe_from_topic(self, user_id: str, topic: str):
        """取消订阅主题"""
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(topic)
            logger.debug(f"[WebSocketManager] 用户 {user_id} 取消订阅主题: {topic}")

    def get_connection_count(self) -> int:
        """获取连接数"""
        return len(self.active_connections)

    def is_user_connected(self, user_id: str) -> bool:
        """检查用户是否在线"""
        return user_id in self.active_connections


manager = ConnectionManager()
