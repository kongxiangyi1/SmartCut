"""
WebSocket网关服务
负责任务订阅和消息路由
"""

import asyncio
import logging
from typing import Dict, Set, List, Any

from backend.core.websocket_manager import manager

logger = logging.getLogger(__name__)


class WebSocketGatewayService:
    """
    WebSocket网关服务
    管理用户与任务的订阅关系，处理消息路由
    """

    def __init__(self):
        self._user_task_subscriptions: Dict[str, Set[str]] = {}
        self._task_users: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        logger.info("[WebSocketGateway] 初始化完成")

    async def subscribe_user_to_task(self, user_id: str, task_id: str) -> bool:
        """
        订阅用户到任务

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            是否成功
        """
        async with self._lock:
            if user_id not in self._user_task_subscriptions:
                self._user_task_subscriptions[user_id] = set()
            self._user_task_subscriptions[user_id].add(task_id)

            if task_id not in self._task_users:
                self._task_users[task_id] = set()
            self._task_users[task_id].add(user_id)

        logger.info(f"[WebSocketGateway] 用户 {user_id} 订阅任务 {task_id}")
        return True

    async def unsubscribe_user_from_task(self, user_id: str, task_id: str) -> bool:
        """
        取消用户对任务的订阅

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            是否成功
        """
        async with self._lock:
            if user_id in self._user_task_subscriptions:
                self._user_task_subscriptions[user_id].discard(task_id)

            if task_id in self._task_users:
                self._task_users[task_id].discard(user_id)
                if not self._task_users[task_id]:
                    del self._task_users[task_id]

        logger.info(f"[WebSocketGateway] 用户 {user_id} 取消订阅任务 {task_id}")
        return True

    async def subscribe_user_to_many_tasks(
        self, user_id: str, task_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        批量订阅用户到任务

        Args:
            user_id: 用户ID
            task_ids: 任务ID列表

        Returns:
            订阅结果
        """
        added = []
        already_subscribed = []

        async with self._lock:
            if user_id not in self._user_task_subscriptions:
                self._user_task_subscriptions[user_id] = set()

            for task_id in task_ids:
                if task_id not in self._user_task_subscriptions[user_id]:
                    self._user_task_subscriptions[user_id].add(task_id)
                    added.append(task_id)
                else:
                    already_subscribed.append(task_id)

                if task_id not in self._task_users:
                    self._task_users[task_id] = set()
                self._task_users[task_id].add(user_id)

        logger.info(f"[WebSocketGateway] 用户 {user_id} 批量订阅: 新增 {len(added)}")
        return {"added": added, "already_subscribed": already_subscribed}

    async def unsubscribe_user_from_many_tasks(
        self, user_id: str, task_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        批量取消用户对任务的订阅

        Args:
            user_id: 用户ID
            task_ids: 任务ID列表

        Returns:
            取消订阅结果
        """
        removed = []
        not_subscribed = []

        async with self._lock:
            if user_id in self._user_task_subscriptions:
                for task_id in task_ids:
                    if task_id in self._user_task_subscriptions[user_id]:
                        self._user_task_subscriptions[user_id].discard(task_id)
                        removed.append(task_id)
                    else:
                        not_subscribed.append(task_id)

                    if task_id in self._task_users:
                        self._task_users[task_id].discard(user_id)
                        if not self._task_users[task_id]:
                            del self._task_users[task_id]

        logger.info(f"[WebSocketGateway] 用户 {user_id} 批量取消订阅: 移除 {len(removed)}")
        return {"removed": removed, "not_subscribed": not_subscribed}

    async def sync_user_subscriptions(
        self, user_id: str, task_ids: Set[str]
    ) -> Dict[str, List[str]]:
        """
        同步用户订阅集

        Args:
            user_id: 用户ID
            task_ids: 目标订阅集

        Returns:
            同步结果
        """
        async with self._lock:
            current_subscriptions = self._user_task_subscriptions.get(user_id, set())

            to_add = task_ids - current_subscriptions
            to_remove = current_subscriptions - task_ids

            if user_id not in self._user_task_subscriptions:
                self._user_task_subscriptions[user_id] = set()

            for task_id in to_add:
                self._user_task_subscriptions[user_id].add(task_id)
                if task_id not in self._task_users:
                    self._task_users[task_id] = set()
                self._task_users[task_id].add(user_id)

            for task_id in to_remove:
                self._user_task_subscriptions[user_id].discard(task_id)
                if task_id in self._task_users:
                    self._task_users[task_id].discard(user_id)
                    if not self._task_users[task_id]:
                        del self._task_users[task_id]

        logger.info(
            f"[WebSocketGateway] 用户 {user_id} 订阅同步: "
            f"新增 {len(to_add)}, 移除 {len(to_remove)}, 未变 {len(task_ids) - len(to_add)}"
        )
        return {
            "added": list(to_add),
            "removed": list(to_remove),
            "unchanged": list(task_ids - to_add)
        }

    async def unsubscribe_user_from_all_tasks(self, user_id: str):
        """
        取消用户所有任务订阅

        Args:
            user_id: 用户ID
        """
        async with self._lock:
            if user_id in self._user_task_subscriptions:
                task_ids = self._user_task_subscriptions[user_id]
                for task_id in task_ids:
                    if task_id in self._task_users:
                        self._task_users[task_id].discard(user_id)
                        if not self._task_users[task_id]:
                            del self._task_users[task_id]
                del self._user_task_subscriptions[user_id]

        logger.info(f"[WebSocketGateway] 用户 {user_id} 取消所有订阅")

    async def broadcast_to_project(self, project_id: str, message: Dict[str, Any]):
        """
        向项目所有订阅者广播消息

        Args:
            project_id: 项目ID
            message: 消息内容
        """
        if project_id in self._task_users:
            user_ids = list(self._task_users[project_id])
            tasks = [
                manager.send_personal_message(message, user_id)
                for user_id in user_ids
                if manager.is_user_connected(user_id)
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.debug(f"[WebSocketGateway] 广播到项目 {project_id}: {len(tasks)} 个用户")

    async def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户订阅状态

        Args:
            user_id: 用户ID

        Returns:
            订阅状态
        """
        async with self._lock:
            subscribed_tasks = list(self._user_task_subscriptions.get(user_id, set()))
            return {
                "user_id": user_id,
                "subscribed_tasks": subscribed_tasks,
                "task_count": len(subscribed_tasks)
            }


websocket_gateway_service = WebSocketGatewayService()
