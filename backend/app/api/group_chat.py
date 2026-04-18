"""
群组聊天 API - 支持文本和文件消息
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile, Form
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
import os
import uuid

from app.db.session import get_db
from app.models.models import User, Group, GroupMember, GroupChatMessage, File as FileModel, Space, Notification
from app.api.deps import get_current_user
from app.core.notifications import manager
from app.core.config import settings
from app.utils.timezone import get_beijing_time

router = APIRouter(prefix="/group-chat", tags=["群组聊天"])


class GroupMessageSend(BaseModel):
    group_id: int
    content: str
    message_type: str = "text"  # text, file, image


@router.post("/messages")
async def send_group_message(
    data: GroupMessageSend,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送群组文本消息"""
    if not data.content or not data.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 检查群组是否存在
    result = await db.execute(select(Group).where(Group.id == data.group_id, Group.status == True))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查用户是否是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == data.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 创建消息
    message = GroupChatMessage(
        group_id=data.group_id,
        sender_id=current_user.id,
        message_type=data.message_type,
        content=data.content.strip()
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # 获取群组所有成员，推送消息
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == data.group_id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()

    msg_data = {
        "id": message.id,
        "group_id": data.group_id,
        "group_name": group.name,
        "sender_id": current_user.id,
        "sender_name": current_user.username,
        "sender_real_name": current_user.real_name,
        "message_type": message.message_type,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }

    for member in members:
        if member.user_id != current_user.id:
            # 创建通知记录
            notification = Notification(
                user_id=member.user_id,
                notification_type="group_chat_message",
                title=f"群组消息 - {group.name}",
                content=f"{current_user.real_name or current_user.username}: {data.content[:50]}{'...' if len(data.content) > 50 else ''}",
                data={
                    "group_id": data.group_id,
                    "group_name": group.name,
                    "sender_id": current_user.id,
                    "sender_name": current_user.username,
                    "sender_real_name": current_user.real_name,
                    "message_id": message.id
                },
                related_id=data.group_id,
                related_type="group"
            )
            db.add(notification)

            # WebSocket推送
            await manager.send_personal_message({
                "type": "group_chat_message",
                "data": msg_data
            }, member.user_id)

    await db.commit()
    return msg_data


@router.post("/messages/file")
async def send_group_file_message(
    group_id: int = Form(...),
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送群组文件消息"""
    # 检查群组是否存在
    result = await db.execute(select(Group).where(Group.id == group_id, Group.status == True))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查用户是否是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 获取群组空间
    result = await db.execute(
        select(Space).where(Space.group_id == group_id, Space.status == True)
    )
    group_space = result.scalar_one_or_none()
    if not group_space:
        raise HTTPException(status_code=400, detail="群组空间不存在")

    # 保存文件
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    stored_name = f"{uuid.uuid4().hex}{file_ext}"

    # 创建群组聊天文件目录
    chat_files_dir = os.path.join(settings.STORAGE_PATH, "chat_files", str(group_id))
    os.makedirs(chat_files_dir, exist_ok=True)

    storage_path = os.path.join(chat_files_dir, stored_name)

    # 写入文件
    content = await file.read()
    file_size = len(content)

    with open(storage_path, "wb") as f:
        f.write(content)

    # 判断文件类型
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    message_type = "image" if file_ext.lower() in image_extensions else "file"

    # 创建文件记录
    file_record = FileModel(
        space_id=group_space.id,
        origin_name=file.filename or stored_name,
        stored_name=stored_name,
        storage_path=storage_path,
        ext=file_ext.lstrip('.'),
        mime_type=file.content_type,
        size=file_size,
        owner_id=current_user.id,
    )
    db.add(file_record)
    await db.flush()

    # 创建消息
    message = GroupChatMessage(
        group_id=group_id,
        sender_id=current_user.id,
        message_type=message_type,
        content=f"[文件] {file.filename}",
        file_id=file_record.id,
        file_name=file.filename,
        file_size=file_size
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # 获取群组所有成员，推送消息
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()

    msg_data = {
        "id": message.id,
        "group_id": group_id,
        "group_name": group.name,
        "sender_id": current_user.id,
        "sender_name": current_user.username,
        "sender_real_name": current_user.real_name,
        "message_type": message_type,
        "content": message.content,
        "file_id": file_record.id,
        "file_name": file.filename,
        "file_size": file_size,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }

    for member in members:
        if member.user_id != current_user.id:
            # 创建通知记录
            notification = Notification(
                user_id=member.user_id,
                notification_type="group_chat_message",
                title=f"群组消息 - {group.name}",
                content=f"{current_user.real_name or current_user.username}: [文件] {file.filename}",
                data={
                    "group_id": group_id,
                    "group_name": group.name,
                    "sender_id": current_user.id,
                    "sender_name": current_user.username,
                    "sender_real_name": current_user.real_name,
                    "message_id": message.id
                },
                related_id=group_id,
                related_type="group"
            )
            db.add(notification)

            # WebSocket推送
            await manager.send_personal_message({
                "type": "group_chat_message",
                "data": msg_data
            }, member.user_id)

    await db.commit()
    return msg_data


@router.get("/messages/{group_id}")
async def get_group_messages(
    group_id: int,
    before_id: int = Query(None, description="获取此ID之前的消息，用于分页"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取群组聊天记录"""
    # 检查用户是否是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 获取消息
    query = select(GroupChatMessage).where(GroupChatMessage.group_id == group_id)

    if before_id:
        query = query.where(GroupChatMessage.id < before_id)

    query = query.order_by(desc(GroupChatMessage.id)).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    # 获取发送者信息
    response = []
    for m in reversed(messages):
        result = await db.execute(select(User).where(User.id == m.sender_id))
        sender = result.scalar_one_or_none()
        response.append({
            "id": m.id,
            "group_id": m.group_id,
            "sender_id": m.sender_id,
            "sender_name": sender.username if sender else "",
            "sender_real_name": sender.real_name if sender else None,
            "message_type": m.message_type or "text",
            "content": m.content,
            "file_id": m.file_id,
            "file_name": m.file_name,
            "file_size": m.file_size,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })

    return response


@router.get("/conversations")
async def get_group_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取群组对话列表"""
    # 获取用户所在的群组
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    memberships = result.scalars().all()

    if not memberships:
        return []

    conversations = []
    for membership in memberships:
        # 获取群组信息
        result = await db.execute(select(Group).where(Group.id == membership.group_id, Group.status == True))
        group = result.scalar_one_or_none()
        if not group:
            continue

        # 获取最后一条消息
        result = await db.execute(
            select(GroupChatMessage).where(
                GroupChatMessage.group_id == group.id
            ).order_by(desc(GroupChatMessage.id)).limit(1)
        )
        last_msg = result.scalar_one_or_none()

        # 格式化最后消息显示
        last_message_text = None
        if last_msg:
            if last_msg.message_type == "file":
                last_message_text = f"[文件] {last_msg.file_name or '文件'}"
            elif last_msg.message_type == "image":
                last_message_text = "[图片]"
            else:
                last_message_text = last_msg.content

        conversations.append({
            "group_id": group.id,
            "group_name": group.name,
            "last_message": last_message_text,
            "last_time": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            "unread_count": 0
        })

    # 按最后消息时间排序
    def get_sort_time(conv):
        if conv["last_time"]:
            from datetime import datetime
            return datetime.fromisoformat(conv["last_time"]).timestamp()
        return 0

    conversations.sort(key=get_sort_time, reverse=True)

    return conversations
