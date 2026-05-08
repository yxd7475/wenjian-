"""
用户管理 API 路由
"""
from typing import Optional, List
import random
import string
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, Department, Role, AuditLog, Space, Folder, File, Friendship
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


async def generate_unique_id(db: AsyncSession, length: int = 8) -> str:
    """生成用户唯一标识码"""
    chars = string.ascii_uppercase + string.digits
    # 排除容易混淆的字符
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')

    max_attempts = 100
    for _ in range(max_attempts):
        # 生成格式: 前缀 "U" + 随机字符
        unique_id = 'U' + ''.join(random.choices(chars, k=length - 1))

        # 检查是否已存在
        result = await db.execute(select(User).where(User.unique_id == unique_id))
        if not result.scalar_one_or_none():
            return unique_id

    # 如果多次尝试都失败，使用更长的ID
    return 'U' + ''.join(random.choices(chars, k=10))


class SimpleUserResponse(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/simple", response_model=List[SimpleUserResponse])
async def get_simple_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户简要列表（用于邀请等功能）"""
    # 超级管理员可以看所有用户
    if current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"]):
        result = await db.execute(
            select(User).where(User.status == True).order_by(User.username)
        )
        users = result.scalars().all()
        return [SimpleUserResponse.model_validate(u) for u in users]

    # 普通用户只能看好友
    from sqlalchemy import or_

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

    # 获取好友用户ID
    friend_ids = set()
    for f in friendships:
        if f.requester_id == current_user.id:
            friend_ids.add(f.addressee_id)
        else:
            friend_ids.add(f.requester_id)

    if not friend_ids:
        return []

    result = await db.execute(
        select(User).where(User.id.in_(friend_ids), User.status == True).order_by(User.username)
    )
    users = result.scalars().all()
    return [SimpleUserResponse.model_validate(u) for u in users]


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
    query = select(User).options(selectinload(User.role))

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

    items = []
    for u in users:
        user_dict = UserResponse.model_validate(u).model_dump()
        size_result = await db.execute(
            select(func.coalesce(func.sum(File.size), 0)).where(
                File.owner_id == u.id,
                File.is_deleted == False
            )
        )
        user_dict['storage_used'] = size_result.scalar() or 0
        items.append(UserResponse(**user_dict))

    return UserListResponse(
        items=items,
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

    # 生成唯一标识码
    unique_id = await generate_unique_id(db)

    # 创建用户
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        real_name=data.real_name,
        email=data.email,
        unique_id=unique_id,
        department_id=data.department_id,
        role_id=data.role_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建个人空间
    space = Space(
        name=f"{user.username} 的个人空间",
        space_type="personal",
        owner_id=user.id,
        description=f"{user.real_name or user.username} 的个人文件空间",
        status=True
    )
    db.add(space)
    await db.commit()
    await db.refresh(space)

    # 创建根文件夹
    root_folder = Folder(
        space_id=space.id,
        parent_id=None,
        name="根目录",
        path="/",
        owner_id=user.id,
        is_deleted=False
    )
    db.add(root_folder)
    await db.commit()

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
    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户信息"""
    # 只能修改自己的信息，或者是管理员
    is_admin = current_user.is_superuser or (current_user.role and current_user.role.code in ('admin', 'super_admin'))
    if user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的信息",
        )

    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
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
    if is_admin:
        if data.department_id is not None:
            user.department_id = data.department_id
        if data.role_id is not None:
            user.role_id = data.role_id
        if data.storage_quota is not None:
            user.storage_quota = data.storage_quota

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

    # 计算用户的已用存储空间
    size_result = await db.execute(
        select(func.coalesce(func.sum(File.size), 0)).where(
            File.owner_id == user.id,
            File.is_deleted == False
        )
    )
    storage_used = size_result.scalar() or 0

    user_dict = UserResponse.model_validate(user).model_dump()
    user_dict['storage_used'] = storage_used
    return UserResponse(**user_dict)


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


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """删除用户 (需要管理员权限)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号",
        )

    # 不能删除超级管理员
    if user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除超级管理员",
        )

    username = user.username
    await db.delete(user)

    # 记录日志
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action="user_delete",
        target_type="user",
        target_id=user_id,
        target_name=username,
        ip=request.client.host if request.client else None,
    )
    db.add(log)
    await db.commit()

    return MessageResponse(message="用户已删除")
