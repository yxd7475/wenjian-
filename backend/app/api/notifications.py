"""
通知 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.models import User, Notification, Friendship, Invitation, Group
from app.api.deps import get_current_user
from app.core.notifications import manager

router = APIRouter(prefix="/notifications", tags=["通知"])


class NotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    content: Optional[str]
    data: Optional[dict]
    related_id: Optional[int]
    related_type: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[dict])
async def get_notifications(
    unread_only: bool = Query(False, description="只获取未读通知"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户通知列表"""
    query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)

    query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()

    response = []
    for n in notifications:
        response.append({
            "id": n.id,
            "notification_type": n.notification_type,
            "title": n.title,
            "content": n.content,
            "data": n.data,
            "related_id": n.related_id,
            "related_type": n.related_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None
        })

    return response


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取未读通知数量"""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()

    # 按类型统计
    type_counts = {}
    for n in notifications:
        t = n.notification_type
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total": len(notifications),
        "by_type": type_counts
    }


@router.get("/pending-invitations")
async def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取待处理的群组邀请"""
    result = await db.execute(
        select(Invitation).where(
            Invitation.invitee_id == current_user.id,
            Invitation.status == "pending"
        )
    )
    invitations = result.scalars().all()

    response = []
    for inv in invitations:
        # 获取群组信息
        group_result = await db.execute(select(Group).where(Group.id == inv.group_id))
        group = group_result.scalar_one_or_none()

        # 获取邀请人信息
        inviter_result = await db.execute(select(User).where(User.id == inv.inviter_id))
        inviter = inviter_result.scalar_one_or_none()

        response.append({
            "invitation_id": inv.id,
            "group_id": inv.group_id,
            "group_name": group.name if group else "未知群组",
            "inviter_id": inv.inviter_id,
            "inviter_name": inviter.real_name or inviter.username if inviter else "未知用户",
            "created_at": inv.created_at.isoformat() if inv.created_at else None
        })

    return response


@router.put("/read-all")
async def mark_all_read(
    notification_type: Optional[str] = Query(None, description="指定通知类型"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知为已读"""
    query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    )

    if notification_type:
        query = query.where(Notification.notification_type == notification_type)

    result = await db.execute(query)
    notifications = result.scalars().all()

    for n in notifications:
        n.is_read = True

    await db.commit()

    return {"message": f"已标记 {len(notifications)} 条通知为已读"}


@router.put("/read-group/{group_id}")
async def mark_group_notifications_read(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记指定群组的消息通知为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.notification_type == "group_chat_message",
            Notification.related_id == group_id,
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()

    for n in notifications:
        n.is_read = True

    await db.commit()

    return {"message": f"已标记 {len(notifications)} 条通知为已读"}


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    await db.commit()

    return {"message": "已标记为已读"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除通知"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    await db.delete(notification)
    await db.commit()

    return {"message": "通知已删除"}
