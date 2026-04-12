"""
用户管理 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, Department, Role, AuditLog
from app.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    PasswordReset,
    MessageResponse,
)
from app.core.security import get_password_hash
from app.api.deps import get_current_user, get_superuser

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    status: Optional[bool] = None,
    department_id: Optional[int] = None,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """获取用户列表 (需要管理员权限)"""
    query = select(User)

    # 筛选条件
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if status is not None:
        query = query.where(User.status == status)
    if department_id:
        query = query.where(User.department_id == department_id)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """创建用户 (需要管理员权限)"""
    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 检查邮箱
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用",
            )

    # 创建用户
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        real_name=data.real_name,
        email=data.email,
        department_id=data.department_id,
        role_id=data.role_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 记录日志
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="user_create",
        target_type="user",
        target_id=user.id,
        target_name=user.username,
        ip=request.client.host if request.client else None,
        detail={"created_user": user.username},
    )
    db.add(log)
    await db.commit()

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """更新用户信息 (需要管理员权限)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 更新字段
    if data.real_name is not None:
        user.real_name = data.real_name
    if data.email is not None:
        user.email = data.email
    if data.department_id is not None:
        user.department_id = data.department_id
    if data.role_id is not None:
        user.role_id = data.role_id

    await db.commit()
    await db.refresh(user)

    # 记录日志
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="user_update",
        target_type="user",
        target_id=user.id,
        target_name=user.username,
        ip=request.client.host if request.client else None,
    )
    db.add(log)
    await db.commit()

    return UserResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=MessageResponse)
async def toggle_user_status(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """切换用户状态 (需要管理员权限)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能禁用自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己的账号",
        )

    user.status = not user.status
    await db.commit()

    # 记录日志
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="user_status_toggle",
        target_type="user",
        target_id=user.id,
        target_name=user.username,
        ip=request.client.host if request.client else None,
        detail={"new_status": user.status},
    )
    db.add(log)
    await db.commit()

    return MessageResponse(message=f"用户已{'启用' if user.status else '禁用'}")


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_user_password(
    user_id: int,
    data: PasswordReset,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """重置用户密码 (需要管理员权限)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    # 记录日志
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="password_reset",
        target_type="user",
        target_id=user.id,
        target_name=user.username,
        ip=request.client.host if request.client else None,
    )
    db.add(log)
    await db.commit()

    return MessageResponse(message="密码重置成功")
