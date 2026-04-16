"""
管理后台 Dashboard API
"""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, File, Folder, AuditLog
from app.api.deps import get_superuser
from app.utils.timezone import get_beijing_time
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["管理后台"])


class FileTypeStat(BaseModel):
    ext: str
    count: int
    size: int
    percentage: float


class ActiveUser(BaseModel):
    username: str
    count: int
    last_active: datetime


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取系统统计"""
    # 用户数
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar()

    # 文件数
    file_count = (await db.execute(
        select(func.count()).select_from(File).where(File.is_deleted == False)
    )).scalar()

    # 文件夹数
    folder_count = (await db.execute(
        select(func.count()).select_from(Folder).where(Folder.is_deleted == False)
    )).scalar()

    # 存储使用
    storage_used = (await db.execute(
        select(func.coalesce(func.sum(File.size), 0)).where(File.is_deleted == False)
    )).scalar() or 0

    return {
        "user_count": user_count,
        "file_count": file_count,
        "folder_count": folder_count,
        "storage_used": storage_used,
    }


@router.get("/large-files", response_model=List[dict])
async def get_large_files(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取大文件排行"""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(File)
        .options(selectinload(File.owner))
        .where(File.is_deleted == False)
        .order_by(desc(File.size))
        .limit(limit)
    )
    files = result.scalars().all()

    result_list = []
    for f in files:
        owner_username = None
        if f.owner:
            owner_username = f.owner.username
        result_list.append({
            "id": f.id,
            "origin_name": f.origin_name,
            "size": f.size,
            "owner": {"username": owner_username},
            "created_at": f.created_at
        })

    return result_list


@router.get("/file-types", response_model=List[FileTypeStat])
async def get_file_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取文件类型分布"""
    # 按扩展名统计
    result = await db.execute(
        select(
            File.ext,
            func.count().label("count"),
            func.sum(File.size).label("size")
        )
        .where(File.is_deleted == False)
        .group_by(File.ext)
        .order_by(desc("count"))
    )
    rows = result.all()

    # 计算总数
    total_count = sum(r.count for r in rows) or 1

    return [
        FileTypeStat(
            ext=r.ext or "其他",
            count=r.count,
            size=r.size or 0,
            percentage=round(r.count / total_count * 100, 1)
        )
        for r in rows[:10]
    ]


@router.get("/active-users", response_model=List[ActiveUser])
async def get_active_users(
    days: int = 7,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取活跃用户"""
    start_date = get_beijing_time() - timedelta(days=days)

    result = await db.execute(
        select(
            AuditLog.username,
            func.count().label("count"),
            func.max(AuditLog.created_at).label("last_active")
        )
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.username)
        .order_by(desc("count"))
        .limit(limit)
    )
    rows = result.all()

    return [ActiveUser(username=r.username, count=r.count, last_active=r.last_active) for r in rows]


@router.get("/risk-operations", response_model=List[dict])
async def get_risk_operations(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取高风险操作记录"""
    risk_actions = [
        "file_delete", "folder_delete", "user_delete", "password_reset",
        "user_status_toggle", "file_permanent_delete", "trash_empty",
        "login"
    ]

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(risk_actions))
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "username": log.username,
            "action": log.action,
            "target_name": log.target_name,
            "ip": log.ip,
            "result": log.result,
            "created_at": log.created_at
        }
        for log in logs
    ]


@router.get("/storage-trend")
async def get_storage_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取存储趋势（简化版）"""
    # 按天统计上传量
    result = await db.execute(
        select(
            func.date(File.created_at).label("date"),
            func.count().label("count"),
            func.sum(File.size).label("size")
        )
        .where(File.created_at >= get_beijing_time() - timedelta(days=days))
        .group_by(func.date(File.created_at))
        .order_by(func.date(File.created_at))
    )
    rows = result.all()

    return [
        {"date": str(r.date), "count": r.count, "size": r.size or 0}
        for r in rows
    ]
