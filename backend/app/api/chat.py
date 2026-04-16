"""
聊天 API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.models import User, Friendship, ChatMessage
from app.api.deps import get_current_user
from app.core.notifications import manager
from app.utils.timezone import get_beijing_time

router = APIRouter(prefix="/chat", tags=["聊天"])


class MessageSend(BaseModel):
    receiver_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    sender_name: str
    sender_real_name: str = None
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    user_id: int
    username: str
    real_name: str = None
    last_message: str = None
    last_time: datetime = None
    unread_count: int = 0

    class Config:
        from_attributes = True


@router.post("/messages")
async def send_message(
    data: MessageSend,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息"""
    if data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能给自己发送消息")

    if not data.content or not data.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 检查是否是好友
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == data.receiver_id),
                and_(Friendship.requester_id == data.receiver_id, Friendship.addressee_id == current_user.id)
            ),
            Friendship.status == "accepted"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="只能给好友发送消息")

    # 检查接收者是否存在
    result = await db.execute(select(User).where(User.id == data.receiver_id, User.status == True))
    receiver = result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 创建消息
    message = ChatMessage(
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        content=data.content.strip()
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    msg_data = {
        "id": message.id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "sender_name": current_user.username,
        "sender_real_name": current_user.real_name,
        "content": message.content,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }

    # 实时推送消息给接收者
    await manager.send_personal_message({
        "type": "chat_message",
        "data": {
            "id": message.id,
            "sender_id": current_user.id,
            "sender_name": current_user.username,
            "sender_real_name": current_user.real_name,
            "receiver_id": data.receiver_id,
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None
        }
    }, data.receiver_id)

    return msg_data


@router.get("/messages/{friend_id}")
async def get_messages(
    friend_id: int,
    before_id: int = Query(None, description="获取此ID之前的消息，用于分页"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取与某好友的聊天记录"""
    # 检查是否是好友
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == friend_id),
                and_(Friendship.requester_id == friend_id, Friendship.addressee_id == current_user.id)
            ),
            Friendship.status == "accepted"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="只能查看好友的聊天记录")

    # 获取消息
    query = select(ChatMessage).where(
        or_(
            and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == friend_id),
            and_(ChatMessage.sender_id == friend_id, ChatMessage.receiver_id == current_user.id)
        )
    )

    if before_id:
        query = query.where(ChatMessage.id < before_id)

    query = query.order_by(desc(ChatMessage.id)).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    # 标记已读
    unread_ids = [m.id for m in messages if m.sender_id == friend_id and not m.is_read]
    if unread_ids:
        await db.execute(
            select(ChatMessage).where(ChatMessage.id.in_(unread_ids))
        )
        for msg in (await db.execute(select(ChatMessage).where(ChatMessage.id.in_(unread_ids)))).scalars().all():
            msg.is_read = True
        await db.commit()

    # 获取好友信息
    result = await db.execute(select(User).where(User.id == friend_id))
    friend = result.scalar_one_or_none()

    response = []
    for m in reversed(messages):  # 按时间正序返回
        sender = current_user if m.sender_id == current_user.id else friend
        response.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "sender_name": sender.username if sender else "",
            "sender_real_name": sender.real_name if sender else None,
            "content": m.content,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })

    return response


@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有对话列表"""
    # 获取好友列表
    result = await db.execute(
        select(Friendship).where(
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.addressee_id == current_user.id
            ),
            Friendship.status == "accepted"
        )
    )
    friendships = result.scalars().all()

    friend_ids = []
    for f in friendships:
        if f.requester_id == current_user.id:
            friend_ids.append(f.addressee_id)
        else:
            friend_ids.append(f.requester_id)

    if not friend_ids:
        return []

    # 获取每个好友的最后一条消息和未读数
    conversations = []
    for friend_id in friend_ids:
        # 获取好友信息
        result = await db.execute(select(User).where(User.id == friend_id))
        friend = result.scalar_one_or_none()
        if not friend:
            continue

        # 获取最后一条消息
        result = await db.execute(
            select(ChatMessage).where(
                or_(
                    and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == friend_id),
                    and_(ChatMessage.sender_id == friend_id, ChatMessage.receiver_id == current_user.id)
                )
            ).order_by(desc(ChatMessage.id)).limit(1)
        )
        last_msg = result.scalar_one_or_none()

        # 获取未读消息数
        result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.sender_id == friend_id,
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False
            )
        )
        unread_count = len(result.scalars().all())

        conversations.append({
            "user_id": friend.id,
            "username": friend.username,
            "real_name": friend.real_name,
            "last_message": last_msg.content if last_msg else None,
            "last_time": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            "unread_count": unread_count
        })

    # 按最后消息时间排序
    def get_sort_time(conv):
        if conv["last_time"]:
            return datetime.fromisoformat(conv["last_time"]).timestamp()
        return 0

    conversations.sort(key=get_sort_time, reverse=True)

    return conversations


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取未读消息总数"""
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.receiver_id == current_user.id,
            ChatMessage.is_read == False
        )
    )
    count = len(result.scalars().all())
    return {"unread_count": count}
