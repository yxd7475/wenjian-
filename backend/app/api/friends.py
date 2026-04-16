"""
好友管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import User, Friendship
from app.api.deps import get_current_user
from app.api.files import log_audit
from app.utils.timezone import get_beijing_time
from app.core.notifications import notify_friend_request, notify_friend_accepted

router = APIRouter(prefix="/friends", tags=["好友管理"])


class FriendRequest(BaseModel):
    user_id: int
    message: Optional[str] = None


class FriendResponse(BaseModel):
    id: int
    friend_id: int
    username: str
    real_name: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class FriendRequestResponse(BaseModel):
    id: int
    requester_id: int
    username: str
    real_name: Optional[str]
    message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class UserSearchResponse(BaseModel):
    id: int
    username: str
    real_name: Optional[str]
    unique_id: Optional[str] = None
    is_friend: bool
    has_pending_request: bool
    is_blocked: bool
    has_blocked_me: bool

    class Config:
        from_attributes = True


@router.get("", response_model=List[FriendResponse])
async def get_friends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的好友列表"""
    # 查询已接受的好友关系
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

    # 获取好友用户信息
    friends = []
    for f in friendships:
        friend_id = f.addressee_id if f.requester_id == current_user.id else f.requester_id
        result = await db.execute(select(User).where(User.id == friend_id))
        user = result.scalar_one_or_none()
        if user and user.status:
            friends.append(FriendResponse(
                id=f.id,
                friend_id=user.id,
                username=user.username,
                real_name=user.real_name,
                created_at=f.created_at.isoformat() if f.created_at else ""
            ))

    return friends


@router.get("/requests", response_model=List[FriendRequestResponse])
async def get_friend_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取收到的好友申请"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        ).order_by(Friendship.created_at.desc())
    )
    requests = result.scalars().all()

    response = []
    for r in requests:
        result = await db.execute(select(User).where(User.id == r.requester_id))
        requester = result.scalar_one_or_none()
        if requester:
            response.append(FriendRequestResponse(
                id=r.id,
                requester_id=requester.id,
                username=requester.username,
                real_name=requester.real_name,
                message=r.message,
                created_at=r.created_at.isoformat() if r.created_at else ""
            ))

    return response


@router.get("/sent", response_model=List[FriendRequestResponse])
async def get_sent_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取发出的好友申请"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == current_user.id,
            Friendship.status.in_(["pending", "rejected"])
        ).order_by(Friendship.created_at.desc())
    )
    requests = result.scalars().all()

    response = []
    for r in requests:
        result = await db.execute(select(User).where(User.id == r.addressee_id))
        addressee = result.scalar_one_or_none()
        if addressee:
            response.append(FriendRequestResponse(
                id=r.id,
                requester_id=current_user.id,
                username=addressee.username,
                real_name=addressee.real_name,
                message=r.message,
                created_at=r.created_at.isoformat() if r.created_at else ""
            ))

    return response


@router.post("/request")
async def send_friend_request(
    data: FriendRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送好友申请"""
    if data.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能向自己发送好友申请")

    # 检查目标用户是否存在
    result = await db.execute(select(User).where(User.id == data.user_id, User.status == True))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否已经是好友或有待处理的申请
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == data.user_id),
                and_(Friendship.requester_id == data.user_id, Friendship.addressee_id == current_user.id)
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.status == "accepted":
            raise HTTPException(status_code=400, detail="你们已经是好友了")
        elif existing.status == "pending":
            if existing.requester_id == current_user.id:
                raise HTTPException(status_code=400, detail="已经发送过好友申请")
            else:
                raise HTTPException(status_code=400, detail="对方已向你发送好友申请，请查看")
        elif existing.status == "blocked":
            if existing.requester_id == data.user_id:
                raise HTTPException(status_code=403, detail="无法向该用户发送申请")
            else:
                # 我拉黑了对方，先解除拉黑
                existing.status = "pending"
                existing.message = data.message
                existing.updated_at = get_beijing_time()
                await db.commit()
                return {"message": "好友申请已发送（已自动解除拉黑）"}

    # 检查对方是否拉黑了我
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == data.user_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "blocked"
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="无法向该用户发送申请")

    # 创建好友申请
    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=data.user_id,
        status="pending",
        message=data.message
    )
    db.add(friendship)
    await db.commit()

    # 发送实时通知
    await notify_friend_request(data.user_id, {
        "id": friendship.id,
        "requester_id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name,
        "message": data.message
    })

    await log_audit(db, current_user, "friend_request", "user", data.user_id, f"发送好友申请", request)

    return {"message": "好友申请已发送"}


@router.post("/{friendship_id}/accept")
async def accept_friend_request(
    friendship_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """接受好友申请"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(status_code=404, detail="好友申请不存在")

    friendship.status = "accepted"
    friendship.updated_at = get_beijing_time()
    await db.commit()

    # 通知申请人
    await notify_friend_accepted(friendship.requester_id, {
        "friendship_id": friendship.id,
        "user_id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name
    })

    await log_audit(db, current_user, "friend_accept", "user", friendship.requester_id, f"接受好友申请", request)

    return {"message": "已成为好友"}


@router.post("/{friendship_id}/reject")
async def reject_friend_request(
    friendship_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝好友申请"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(status_code=404, detail="好友申请不存在")

    friendship.status = "rejected"
    friendship.updated_at = get_beijing_time()
    await db.commit()

    await log_audit(db, current_user, "friend_reject", "user", friendship.requester_id, f"拒绝好友申请", request)

    return {"message": "已拒绝好友申请"}


@router.delete("/{friendship_id}")
async def delete_friend(
    friendship_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除好友"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.id == friendship_id,
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.addressee_id == current_user.id
            ),
            Friendship.status == "accepted"
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(status_code=404, detail="好友关系不存在")

    friend_id = friendship.addressee_id if friendship.requester_id == current_user.id else friendship.requester_id

    await db.delete(friendship)
    await db.commit()

    await log_audit(db, current_user, "friend_delete", "user", friend_id, f"删除好友", request)

    return {"message": "已删除好友"}


@router.post("/{user_id}/block")
async def block_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拉黑用户"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能拉黑自己")

    # 检查目标用户是否存在
    result = await db.execute(select(User).where(User.id == user_id, User.status == True))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否已有关系记录
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == user_id),
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == current_user.id)
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.requester_id == current_user.id:
            # 我发起的关系，直接改为拉黑
            existing.status = "blocked"
            existing.updated_at = get_beijing_time()
        else:
            # 对方发起的关系，删除后创建新的拉黑记录
            await db.delete(existing)
            new_block = Friendship(
                requester_id=current_user.id,
                addressee_id=user_id,
                status="blocked"
            )
            db.add(new_block)
    else:
        # 创建新的拉黑记录
        new_block = Friendship(
            requester_id=current_user.id,
            addressee_id=user_id,
            status="blocked"
        )
        db.add(new_block)

    await db.commit()

    await log_audit(db, current_user, "user_block", "user", user_id, f"拉黑用户", request)

    return {"message": "已拉黑该用户"}


@router.delete("/{user_id}/block")
async def unblock_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消拉黑"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == current_user.id,
            Friendship.addressee_id == user_id,
            Friendship.status == "blocked"
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(status_code=404, detail="拉黑记录不存在")

    await db.delete(friendship)
    await db.commit()

    await log_audit(db, current_user, "user_unblock", "user", user_id, f"取消拉黑", request)

    return {"message": "已取消拉黑"}


@router.get("/blocked", response_model=List[dict])
async def get_blocked_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取黑名单列表"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == current_user.id,
            Friendship.status == "blocked"
        ).order_by(Friendship.created_at.desc())
    )
    blocked = result.scalars().all()

    response = []
    for b in blocked:
        result = await db.execute(select(User).where(User.id == b.addressee_id))
        user = result.scalar_one_or_none()
        if user:
            response.append({
                "id": b.id,
                "user_id": user.id,
                "username": user.username,
                "real_name": user.real_name,
                "created_at": b.created_at.isoformat() if b.created_at else ""
            })

    return response


@router.get("/search", response_model=List[UserSearchResponse])
async def search_users(
    keyword: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索用户 - 支持用户名、姓名、唯一标识码搜索"""
    # 尝试精确匹配唯一标识码（优先）
    keyword_upper = keyword.upper()
    result = await db.execute(
        select(User).where(
            User.status == True,
            User.unique_id == keyword_upper
        )
    )
    exact_match = result.scalar_one_or_none()

    # 搜索用户名或真实姓名包含关键词的用户
    result = await db.execute(
        select(User).where(
            User.status == True,
            or_(
                User.username.ilike(f"%{keyword}%"),
                User.real_name.ilike(f"%{keyword}%")
            )
        ).limit(20)
    )
    users = list(result.scalars().all())

    # 如果有精确匹配，确保在最前面
    if exact_match and exact_match not in users:
        users.insert(0, exact_match)

    # 排除自己
    users = [u for u in users if u.id != current_user.id]

    # 获取与这些用户的好友关系
    user_ids = [u.id for u in users]
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id.in_(user_ids)),
                and_(Friendship.requester_id.in_(user_ids), Friendship.addressee_id == current_user.id)
            )
        )
    )
    friendships = result.scalars().all()

    # 构建关系映射
    relation_map = {}
    for f in friendships:
        other_id = f.addressee_id if f.requester_id == current_user.id else f.requester_id
        relation_map[other_id] = f

    response = []
    for user in users:
        f = relation_map.get(user.id)
        is_friend = bool(f and f.status == "accepted")
        has_pending = bool(f and f.status == "pending")
        is_blocked = bool(f and f.status == "blocked" and f.requester_id == current_user.id)
        has_blocked_me = bool(f and f.status == "blocked" and f.addressee_id == current_user.id)

        response.append(UserSearchResponse(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            unique_id=user.unique_id,
            is_friend=is_friend,
            has_pending_request=has_pending,
            is_blocked=is_blocked,
            has_blocked_me=has_blocked_me
        ))

    return response
