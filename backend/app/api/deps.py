"""
API依赖项
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.models import User, Permission, RolePermission
from app.core.security import decode_access_token

# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前用户"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌内容",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户"""
    if not current_user.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user


async def get_superuser(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """验证管理员权限(超级管理员或admin角色)"""
    if current_user.is_superuser:
        return current_user

    # 检查是否是 admin 角色
    from app.models.models import Role
    if current_user.role_id:
        result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = result.scalar_one_or_none()
        if role and role.code in ('admin', 'super_admin'):
            return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="需要管理员权限",
    )


async def check_permission(
    permission_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """检查用户权限"""
    # 超级管理员拥有所有权限
    if current_user.is_superuser:
        return current_user

    if not current_user.role_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户未分配角色",
        )

    # 查询权限
    result = await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == current_user.role_id)
        .where(Permission.code == permission_code)
    )
    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"没有 {permission_code} 权限",
        )

    return current_user


def require_permission(permission_code: str):
    """权限装饰器工厂"""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        return await check_permission(permission_code, current_user, db)
    return permission_checker


async def check_space_access(
    space_id: int,
    current_user: User,
    db: AsyncSession,
) -> "Space":
    """检查空间访问权限并返回空间对象"""
    from app.models.models import Space, GroupMember

    result = await db.execute(
        select(Space).where(Space.id == space_id)
    )
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="空间不存在"
        )

    if space.space_type == "admin":
        if not (current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此空间"
            )

    elif space.space_type == "personal":
        if space.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此空间"
            )

    elif space.space_type == "group":
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == space.group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.join_status == "active"
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此空间"
            )

    return space


async def get_space_role(
    space_id: int,
    current_user: User,
    db: AsyncSession,
) -> str:
    """获取用户在空间中的角色"""
    from app.models.models import Space, GroupMember

    result = await db.execute(
        select(Space).where(Space.id == space_id)
    )
    space = result.scalar_one_or_none()

    if not space:
        return "none"

    if space.space_type == "admin":
        if current_user.is_superuser or (current_user.role and current_user.role.code == "super_admin"):
            return "owner"
        elif current_user.role and current_user.role.code == "admin":
            return "manager"
        return "none"

    elif space.space_type == "personal":
        if space.owner_id == current_user.id:
            return "owner"
        return "none"

    elif space.space_type == "group":
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == space.group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.join_status == "active"
            )
        )
        member = result.scalar_one_or_none()
        if member:
            return member.role
        return "none"

    return "none"
