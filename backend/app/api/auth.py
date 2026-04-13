"""
认证相关 API 路由
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.models import User, AuditLog
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
