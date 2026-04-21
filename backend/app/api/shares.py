"""
文件分享 API
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from app.utils.share_code import generate_share_code
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, File, FileShare, AuditLog
from app.api.deps import get_current_user
from app.api.files import log_audit
from app.utils.timezone import utc_to_beijing

router = APIRouter(prefix="/shares", tags=["文件分享"])


class ShareCreate(BaseModel):
    file_id: int
    password: Optional[str] = None
    expire_hours: int = 24  # 过期时间（小时）
    max_downloads: int = 0  # 最大下载次数，0表示不限


class ShareResponse(BaseModel):
    id: int
    share_code: str
    file_name: str
    file_size: int
    password: Optional[str]
    expire_at: Optional[datetime]
    max_downloads: int
    download_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ShareInfo(BaseModel):
    id: int
    file_name: str
    file_size: int
    has_password: bool
    expire_at: Optional[datetime]
    download_count: int
    max_downloads: int
    is_active: bool


@router.post("", response_model=ShareResponse)
async def create_share(
    data: ShareCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建文件分享链接"""
    # 检查文件
    result = await db.execute(
        select(File).where(File.id == data.file_id).where(File.is_deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 检查权限
    if file.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限分享此文件")

    # 生成分享码（确保唯一）
    share_code = generate_share_code()
    # 如果冲突，重新生成
    for _ in range(10):
        existing = await db.execute(
            select(FileShare).where(FileShare.share_code == share_code)
        )
        if not existing.scalar_one_or_none():
            break
        share_code = generate_share_code()

    # 计算过期时间（使用 UTC 存储，兼容已有数据）
    expire_at = None
    if data.expire_hours > 0:
        expire_at = datetime.utcnow() + timedelta(hours=data.expire_hours)

    # 创建分享记录
    share = FileShare(
        file_id=file.id,
        share_code=share_code,
        password=data.password,
        created_by=current_user.id,
        expire_at=expire_at,
        max_downloads=data.max_downloads,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    await log_audit(
        db, current_user, "file_share", "file", file.id,
        file.origin_name, request, detail={"share_code": share_code}
    )

    return ShareResponse(
        id=share.id,
        share_code=share.share_code,
        file_name=file.origin_name,
        file_size=file.size,
        password=share.password,
        expire_at=utc_to_beijing(share.expire_at),  # 转换为北京时间显示
        max_downloads=share.max_downloads,
        download_count=share.download_count,
        is_active=share.is_active,
        created_at=utc_to_beijing(share.created_at)  # 转换为北京时间显示
    )


@router.get("/my", response_model=List[ShareResponse])
async def get_my_shares(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我创建的分享列表"""
    result = await db.execute(
        select(FileShare)
        .where(FileShare.created_by == current_user.id)
        .options(selectinload(FileShare.file))
        .order_by(FileShare.created_at.desc())
    )
    shares = result.scalars().all()

    return [
        ShareResponse(
            id=s.id,
            share_code=s.share_code,
            file_name=s.file.origin_name if s.file else "文件已删除",
            file_size=s.file.size if s.file else 0,
            password=s.password,
            expire_at=utc_to_beijing(s.expire_at),  # 转换为北京时间显示
            max_downloads=s.max_downloads,
            download_count=s.download_count,
            is_active=s.is_active,
            created_at=utc_to_beijing(s.created_at)  # 转换为北京时间显示
        )
        for s in shares
    ]


@router.get("/{share_code}", response_model=ShareInfo)
async def get_share_info(
    share_code: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分享信息（公开接口）"""
    result = await db.execute(
        select(FileShare)
        .where(FileShare.share_code == share_code)
        .options(selectinload(FileShare.file))
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="分享不存在")

    if not share.is_active:
        raise HTTPException(status_code=400, detail="分享已关闭")

    # 使用 UTC 时间比较（数据库存储的是 UTC）
    if share.expire_at and share.expire_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="分享已过期")

    if share.max_downloads > 0 and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=400, detail="下载次数已用完")

    if not share.file or share.file.is_deleted:
        raise HTTPException(status_code=404, detail="文件不存在")

    return ShareInfo(
        id=share.id,
        file_name=share.file.origin_name,
        file_size=share.file.size,
        has_password=bool(share.password),
        expire_at=utc_to_beijing(share.expire_at),  # 转换为北京时间显示
        download_count=share.download_count,
        max_downloads=share.max_downloads,
        is_active=share.is_active
    )


@router.post("/{share_code}/verify")
async def verify_share_password(
    share_code: str,
    data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """验证分享密码"""
    password = data.get("password")

    result = await db.execute(
        select(FileShare)
        .where(FileShare.share_code == share_code)
        .options(selectinload(FileShare.file))
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="分享不存在")

    if not share.is_active:
        raise HTTPException(status_code=400, detail="分享已关闭")

    # 使用 UTC 时间比较
    if share.expire_at and share.expire_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="分享已过期")

    if share.max_downloads > 0 and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=400, detail="下载次数已用完")

    if not share.file or share.file.is_deleted:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 验证密码
    if share.password:
        if not password or share.password != password:
            raise HTTPException(status_code=403, detail="密码错误")

    return {"verified": True}


@router.post("/{share_code}/download")
async def download_shared_file(
    share_code: str,
    data: dict = Body(default={}),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """下载分享文件"""
    password = data.get("password") if data else None

    result = await db.execute(
        select(FileShare)
        .where(FileShare.share_code == share_code)
        .options(selectinload(FileShare.file))
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="分享不存在")

    if not share.is_active:
        raise HTTPException(status_code=400, detail="分享已关闭")

    # 使用 UTC 时间比较
    if share.expire_at and share.expire_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="分享已过期")

    if share.max_downloads > 0 and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=400, detail="下载次数已用完")

    # 验证密码
    if share.password and share.password != password:
        raise HTTPException(status_code=403, detail="密码错误")

    if not share.file or share.file.is_deleted:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not os.path.exists(share.file.storage_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 更新下载次数
    share.download_count += 1
    await db.commit()

    return FileResponse(
        path=share.file.storage_path,
        filename=share.file.origin_name,
        media_type=share.file.mime_type or "application/octet-stream"
    )


@router.put("/{share_id}/toggle")
async def toggle_share(
    share_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开启/关闭分享"""
    result = await db.execute(
        select(FileShare).where(FileShare.id == share_id)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="分享不存在")

    if share.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限操作")

    share.is_active = not share.is_active
    await db.commit()

    action = "share_enable" if share.is_active else "share_disable"
    await log_audit(
        db, current_user, action, "share", share.id,
        share.share_code, request
    )

    return {"message": "已" + ("开启" if share.is_active else "关闭") + "分享", "is_active": share.is_active}


@router.delete("/{share_id}")
async def delete_share(
    share_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除分享"""
    result = await db.execute(
        select(FileShare).where(FileShare.id == share_id)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="分享不存在")

    if share.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限操作")

    await db.delete(share)
    await db.commit()

    await log_audit(
        db, current_user, "share_delete", "share", share.id,
        share.share_code, request
    )

    return {"message": "分享已删除"}
