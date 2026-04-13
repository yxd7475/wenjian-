"""
文件版本管理 API
"""
import os
import shutil
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, File, FileVersion, AuditLog
from app.api.deps import get_current_user
from app.api.files import log_audit
from app.utils.timezone import get_beijing_time

router = APIRouter(prefix="/versions", tags=["文件版本"])


class VersionResponse(BaseModel):
    id: int
    version_no: int
    size: int
    hash_sha256: Optional[str]
    creator_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{file_id}", response_model=List[VersionResponse])
async def get_versions(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取文件版本历史"""
    # 检查文件是否存在
    result = await db.execute(
        select(File).where(File.id == file_id).where(File.is_deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 获取版本历史
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.file_id == file_id)
        .options(selectinload(FileVersion.creator))
        .order_by(desc(FileVersion.version_no))
    )
    versions = result.scalars().all()

    return [
        VersionResponse(
            id=v.id,
            version_no=v.version_no,
            size=v.size,
            hash_sha256=v.hash_sha256,
            creator_name=v.creator.real_name or v.creator.username if v.creator else None,
            created_at=v.created_at
        )
        for v in versions
    ]


@router.post("/{file_id}/rollback/{version_no}")
async def rollback_version(
    file_id: int,
    version_no: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回滚到指定版本"""
    # 检查文件是否存在
    result = await db.execute(
        select(File).where(File.id == file_id).where(File.is_deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 检查权限（只有所有者可以回滚）
    if file.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限操作此文件")

    # 获取目标版本
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.file_id == file_id)
        .where(FileVersion.version_no == version_no)
    )
    target_version = result.scalar_one_or_none()
    if not target_version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 保存当前版本为新版本
    if os.path.exists(file.storage_path):
        # 创建新版本记录
        new_version_no = file.version_no + 1
        new_version = FileVersion(
            file_id=file.id,
            version_no=new_version_no,
            storage_path=file.storage_path,
            size=file.size,
            hash_sha256=file.hash_sha256,
            created_by=current_user.id
        )
        db.add(new_version)

        # 复制当前文件到版本存储
        version_dir = os.path.join(os.path.dirname(file.storage_path), "versions")
        os.makedirs(version_dir, exist_ok=True)
        new_version_path = os.path.join(version_dir, f"{file_id}_v{file.version_no}")
        shutil.copy2(file.storage_path, new_version_path)
        new_version.storage_path = new_version_path

    # 恢复目标版本
    if os.path.exists(target_version.storage_path):
        shutil.copy2(target_version.storage_path, file.storage_path)
        file.size = target_version.size
        file.hash_sha256 = target_version.hash_sha256
        file.version_no = file.version_no + 1
        file.updated_at = get_beijing_time()

    await db.commit()

    # 记录审计日志
    await log_audit(
        db, current_user, "version_rollback", "file", file.id,
        file.origin_name, request, detail={"version": version_no}
    )

    return {"message": f"已回滚到版本 {version_no}"}


@router.delete("/{file_id}/version/{version_id}")
async def delete_version(
    file_id: int,
    version_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定版本（保留当前版本）"""
    # 检查文件
    result = await db.execute(
        select(File).where(File.id == file_id).where(File.is_deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 检查权限
    if file.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限操作此文件")

    # 获取版本
    result = await db.execute(
        select(FileVersion).where(FileVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if not version or version.file_id != file_id:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 不能删除当前版本
    if version.version_no == file.version_no:
        raise HTTPException(status_code=400, detail="不能删除当前版本")

    # 删除版本文件
    if version.storage_path and os.path.exists(version.storage_path):
        os.remove(version.storage_path)

    await db.delete(version)
    await db.commit()

    await log_audit(
        db, current_user, "version_delete", "file", file.id,
        file.origin_name, request, detail={"version_no": version.version_no}
    )

    return {"message": "版本已删除"}
