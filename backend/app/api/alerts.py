"""
审计告警 API
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, AuditLog, AuditAlert, File
from app.api.deps import get_current_user, get_superuser
from app.api.files import log_audit
from app.utils.timezone import get_beijing_time
from app.core.notifications import manager

router = APIRouter(prefix="/alerts", tags=["审计告警"])


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    content: Optional[str]
    username: Optional[str]
    is_read: bool
    is_handled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertStats(BaseModel):
    total: int
    unread: int
    danger: int
    warning: int
    info: int


async def create_alert(
    db,
    alert_type: str,
    severity: str,
    title: str,
    content: str = None,
    user_id: int = None,
    username: str = None
):
    """创建告警记录"""
    alert = AuditAlert(
        alert_type=alert_type,
        severity=severity,
        title=title,
        content=content,
        user_id=user_id,
        username=username
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    # 实时推送告警给所有管理员
    await broadcast_alert_to_admins(db, {
        "id": alert.id,
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "content": content,
        "username": username,
        "created_at": alert.created_at.isoformat()
    })

    return alert


async def broadcast_alert_to_admins(db, alert_data):
    """向所有管理员推送告警"""
    # 获取所有管理员用户
    result = await db.execute(
        select(User).where(User.role_id == 1, User.status == True)  # role_id=1 是管理员
    )
    admins = result.scalars().all()

    # 推送告警给每个管理员
    for admin in admins:
        await manager.send_personal_message({
            "type": "alert",
            "data": alert_data
        }, admin.id)


async def check_and_create_alerts(db, action: str, user: User, target_name: str, result: bool, detail: dict = None):
    """检查并创建相关告警"""
    # 敏感文件下载告警
    if action == "file_download" and result:
        # 检查是否为敏感文件（可以根据文件名或扩展名判断）
        sensitive_keywords = ["机密", "秘密", "confidential", "secret", "password", "账号", "财务"]
        for keyword in sensitive_keywords:
            if keyword.lower() in target_name.lower():
                await create_alert(
                    db, "sensitive_download", "warning",
                    f"敏感文件下载告警",
                    f"用户 {user.username} 下载了可能包含敏感信息的文件：{target_name}",
                    user.id, user.username
                )
                break

    # 批量删除告警
    if action == "batch_delete" and result:
        count = detail.get("count", 1) if detail else 1
        if count >= 5:
            await create_alert(
                db, "batch_delete", "danger",
                f"批量删除告警",
                f"用户 {user.username} 批量删除了 {count} 个文件/文件夹",
                user.id, user.username
            )

    # 登录失败告警
    if action == "login" and not result:
        # 检查短时间内登录失败次数
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.action == "login")
            .where(AuditLog.result == False)
            .where(AuditLog.created_at >= get_beijing_time() - timedelta(minutes=15))
            .where(AuditLog.username == user.username if user else None)
        )
        failed_logins = result.scalars().all()
        if len(failed_logins) >= 3:
            await create_alert(
                db, "login_failed", "danger",
                f"多次登录失败告警",
                f"用户 {user.username if user else '未知'} 在15分钟内登录失败 {len(failed_logins)} 次",
                user.id if user else None, user.username if user else None
            )

    # 高权限操作追踪
    high_privilege_actions = ["user_delete", "role_change", "password_reset", "backup_restore", "trash_empty"]
    if action in high_privilege_actions and result:
        await create_alert(
            db, "high_privilege", "warning",
            f"高权限操作告警",
            f"用户 {user.username} 执行了高权限操作：{action}，目标：{target_name}",
            user.id, user.username
        )


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    severity: str = None,
    is_read: bool = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取告警列表"""
    query = select(AuditAlert).order_by(desc(AuditAlert.created_at))

    if severity:
        query = query.where(AuditAlert.severity == severity)
    if is_read is not None:
        query = query.where(AuditAlert.is_read == is_read)

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            title=a.title,
            content=a.content,
            username=a.username,
            is_read=a.is_read,
            is_handled=a.is_handled,
            created_at=a.created_at
        )
        for a in alerts
    ]


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取告警统计"""
    # 总数
    total_result = await db.execute(select(AuditAlert))
    total = len(total_result.scalars().all())

    # 未读数
    unread_result = await db.execute(
        select(AuditAlert).where(AuditAlert.is_read == False)
    )
    unread = len(unread_result.scalars().all())

    # 各级别数量
    danger_result = await db.execute(
        select(AuditAlert).where(AuditAlert.severity == "danger").where(AuditAlert.is_handled == False)
    )
    danger = len(danger_result.scalars().all())

    warning_result = await db.execute(
        select(AuditAlert).where(AuditAlert.severity == "warning").where(AuditAlert.is_handled == False)
    )
    warning = len(warning_result.scalars().all())

    info_result = await db.execute(
        select(AuditAlert).where(AuditAlert.severity == "info").where(AuditAlert.is_handled == False)
    )
    info = len(info_result.scalars().all())

    return AlertStats(
        total=total,
        unread=unread,
        danger=danger,
        warning=warning,
        info=info
    )


@router.put("/{alert_id}/read")
async def mark_alert_read(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """标记告警为已读"""
    result = await db.execute(
        select(AuditAlert).where(AuditAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    alert.is_read = True
    await db.commit()

    return {"message": "已标记为已读"}


@router.put("/{alert_id}/handle")
async def handle_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """标记告警为已处理"""
    result = await db.execute(
        select(AuditAlert).where(AuditAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    alert.is_read = True
    alert.is_handled = True
    await db.commit()

    return {"message": "已标记为已处理"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """标记所有告警为已读"""
    result = await db.execute(
        select(AuditAlert).where(AuditAlert.is_read == False)
    )
    alerts = result.scalars().all()

    for alert in alerts:
        alert.is_read = True

    await db.commit()

    return {"message": f"已标记 {len(alerts)} 条告警为已读"}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """删除告警"""
    result = await db.execute(
        select(AuditAlert).where(AuditAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    await db.delete(alert)
    await db.commit()

    return {"message": "告警已删除"}
