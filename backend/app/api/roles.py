"""
角色管理 API 路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, Role, Permission, RolePermission
from app.schemas import RoleResponse, RoleCreate, RoleUpdate
from app.api.deps import get_current_user, get_superuser
from pydantic import BaseModel

router = APIRouter(prefix="/roles", tags=["角色管理"])


class RoleDetail(RoleResponse):
    permissions: List[dict] = []


class PermissionResponse(BaseModel):
    id: int
    code: str
    name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[RoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()
    return roles


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """获取权限列表（管理员）"""
    result = await db.execute(select(Permission).order_by(Permission.category, Permission.id))
    permissions = result.scalars().all()
    return permissions


@router.get("/{role_id}", response_model=RoleDetail)
async def get_role(
    role_id: int,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """获取角色详情"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 获取角色权限
    result = await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    permissions = result.scalars().all()

    return RoleDetail(
        **{k: getattr(role, k) for k in RoleResponse.model_fields.keys()},
        permissions=[{"id": p.id, "code": p.code, "name": p.name} for p in permissions]
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """更新角色权限"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可修改")

    if data.name:
        role.name = data.name
    if data.description:
        role.description = data.description

    if data.permission_ids is not None:
        # 删除旧权限
        result = await db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        for rp in result.scalars().all():
            await db.delete(rp)

        # 添加新权限
        for perm_id in data.permission_ids:
            rp = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(rp)

    await db.commit()
    await db.refresh(role)
    return role
