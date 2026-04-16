"""
WebSocket 通知管理
"""
from typing import Dict, Set
from fastapi import WebSocket
import json
import asyncio


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 用户ID -> WebSocket连接集合
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """建立连接"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        """断开连接"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        """发送个人消息"""
        if user_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)

            # 清理断开的连接
            for conn in dead_connections:
                self.disconnect(conn, user_id)

    async def broadcast_to_users(self, message: dict, user_ids: list):
        """广播消息给多个用户"""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def broadcast_all(self, message: dict):
        """广播消息给所有用户"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)


# 全局连接管理器
manager = ConnectionManager()


async def notify_invitation(user_id: int, invitation_data: dict):
    """通知用户收到新邀请"""
    await manager.send_personal_message({
        "type": "invitation",
        "data": invitation_data
    }, user_id)


async def notify_group_member(group_id: int, member_data: dict, member_ids: list):
    """通知群组成员有新成员加入"""
    await manager.broadcast_to_users({
        "type": "group_member_joined",
        "data": {
            "group_id": group_id,
            "member": member_data
        }
    }, member_ids)


async def notify_new_file(group_id: int, file_data: dict, member_ids: list):
    """通知群组成员有新文件上传"""
    await manager.broadcast_to_users({
        "type": "new_file",
        "data": {
            "group_id": group_id,
            "file": file_data
        }
    }, member_ids)


async def notify_file_deleted(group_id: int, file_id: int, member_ids: list):
    """通知群组成员文件被删除"""
    await manager.broadcast_to_users({
        "type": "file_deleted",
        "data": {
            "group_id": group_id,
            "file_id": file_id
        }
    }, member_ids)


async def notify_invitation_accepted(user_id: int, group_data: dict):
    """通知邀请人邀请被接受"""
    await manager.send_personal_message({
        "type": "invitation_accepted",
        "data": group_data
    }, user_id)


async def notify_group_dissolved(group_id: int, member_ids: list):
    """通知群组成员群组已解散"""
    await manager.broadcast_to_users({
        "type": "group_dissolved",
        "data": {
            "group_id": group_id
        }
    }, member_ids)


async def notify_friend_request(user_id: int, requester_data: dict):
    """通知用户收到好友申请"""
    await manager.send_personal_message({
        "type": "friend_request",
        "data": requester_data
    }, user_id)


async def notify_friend_accepted(user_id: int, friend_data: dict):
    """通知好友申请被接受"""
    await manager.send_personal_message({
        "type": "friend_accepted",
        "data": friend_data
    }, user_id)
