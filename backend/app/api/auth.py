"""
认证相关 API 路由
"""
from datetime import datetime
from typing import Optional
import random
import string
import socket
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, AuditLog, Space, Folder, Role
from app.schemas import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    PasswordChange,
    MessageResponse,
)
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.api.deps import get_current_user
from app.utils.timezone import get_beijing_time

router = APIRouter(prefix="/auth", tags=["认证"])


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


async def log_audit(
    db: AsyncSession,
    user_id: int,
    username: str,
    action: str,
    request: Request,
    result: bool = True,
    detail: dict = None,
):
    """记录审计日志"""
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
        result=result,
        detail=detail,
    )
    db.add(log)
    await db.commit()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录"""
    # 调试日志
    print(f"[DEBUG] Login request - username: {data.username}, password: {'*' * len(data.password)}")

    # 查询用户（加载role关系）
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.username == data.username)
    )
    user = result.scalar_one_or_none()

    # 验证用户和密码
    if not user or not verify_password(data.password, user.password_hash):
        # 记录失败日志
        if user:
            await log_audit(
                db, user.id, data.username, "login", request,
                result=False, detail={"reason": "密码错误"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 检查用户状态
    if not user.status:
        await log_audit(
            db, user.id, user.username, "login", request,
            result=False, detail={"reason": "用户已禁用"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 确保用户有个人空间
    result = await db.execute(
        select(Space).where(
            Space.space_type == "personal",
            Space.owner_id == user.id
        )
    )
    personal_space = result.scalar_one_or_none()
    if not personal_space:
        personal_space = Space(
            name=f"{user.username} 的个人空间",
            space_type="personal",
            owner_id=user.id,
            description=f"{user.real_name or user.username} 的个人文件空间",
            status=True,
        )
        db.add(personal_space)
        await db.commit()

    # 更新最后登录时间
    user.last_login = get_beijing_time()
    await db.commit()

    # 生成令牌
    access_token = create_access_token(data={"sub": str(user.id)})

    # 记录成功日志
    await log_audit(db, user.id, user.username, "login", request)

    return LoginResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户登出"""
    await log_audit(
        db, current_user.id, current_user.username, "logout", request
    )
    return MessageResponse(message="登出成功")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    # 重新查询以加载role关系
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()
    return UserResponse.model_validate(user)


@router.put("/password", response_model=MessageResponse)
async def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )

    # 更新密码
    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    await log_audit(
        db, current_user.id, current_user.username,
        "password_change", request
    )

    return MessageResponse(message="密码修改成功")


class RegisterRequest(BaseModel):
    username: str
    password: str
    real_name: Optional[str] = None
    email: Optional[str] = None


@router.post("/register", response_model=LoginResponse)
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户注册"""
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

    # 获取普通用户角色
    result = await db.execute(select(Role).where(Role.code == "user"))
    user_role = result.scalar_one_or_none()

    # 生成唯一标识码
    unique_id = await generate_unique_id(db)

    # 创建用户
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        real_name=data.real_name or data.username,
        email=data.email,
        unique_id=unique_id,
        role_id=user_role.id if user_role else None,
        status=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建个人空间
    space = Space(
        name=f"{user.username} 的个人空间",
        space_type="personal",
        owner_id=user.id,
        description=f"{user.real_name} 的个人文件空间",
        status=True,
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
        is_deleted=False,
    )
    db.add(root_folder)
    await db.commit()

    # 记录审计日志
    await log_audit(db, user.id, user.username, "register", request)

    # 自动登录 - 生成令牌
    access_token = create_access_token(data={"sub": str(user.id)})

    # 重新加载用户以获取role关系
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    user = result.scalar_one()

    return LoginResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/server-info")
async def get_server_info():
    """获取服务器信息（局域网 IP 等）- 无需认证"""
    # 获取本机所有 IP 地址
    hostname = socket.gethostname()
    local_ips = []

    try:
        # 获取所有网络接口的 IP
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            # 过滤掉 IPv6 和回环地址
            if ':' not in ip and ip != '127.0.0.1':
                if ip not in local_ips:
                    local_ips.append(ip)
    except Exception:
        pass

    # 如果没有找到，尝试连接外部地址来获取本机 IP
    if not local_ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass

    return {
        "hostname": hostname,
        "local_ips": local_ips,
        "port": 8088  # 后端端口
    }
