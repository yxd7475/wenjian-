"""
群组管理 API
"""
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import User, Group, GroupMember, Space, Folder
from app.api.deps import get_current_user
from app.api.files import log_audit

router = APIRouter(prefix="/groups", tags=["群组管理"])


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public_join: Optional[bool] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    invite_code: Optional[str]
    is_public_join: bool
    status: bool
    member_count: int = 0
    space_id: Optional[int] = None

    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    id: int
    user_id: int
    username: str
    real_name: Optional[str]
    role: str
    join_status: str
    joined_at: str

    class Config:
        from_attributes = True


def generate_invite_code():
    """生成邀请码"""
    return secrets.token_urlsafe(8)


@router.post("", response_model=GroupResponse)
async def create_group(
    data: GroupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建群组"""
    # 创建群组
    group = Group(
        name=data.name,
        description=data.description,
        owner_id=current_user.id,
        invite_code=generate_invite_code(),
        is_public_join=False,
        status=True
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    # 创建群组空间
    space = Space(
        name=f"{data.name} 空间",
        space_type="group",
        group_id=group.id,
        description=f"群组 {data.name} 的协作空间",
        status=True
    )
    db.add(space)
    await db.commit()
    await db.refresh(space)

    # 创建群主成员记录
    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="owner",
        join_status="active",
        invited_by=current_user.id
    )
    db.add(member)
    await db.commit()

    await log_audit(db, current_user, "group_create", "group", group.id, f"创建群组: {group.name}", request)

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        invite_code=group.invite_code,
        is_public_join=group.is_public_join,
        status=group.status,
        member_count=1,
        space_id=space.id
    )


@router.get("", response_model=List[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我的群组列表"""
    # 查询用户所在的群组
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    memberships = result.scalars().all()
    group_ids = [m.group_id for m in memberships]

    if not group_ids:
        return []

    result = await db.execute(
        select(Group).where(Group.id.in_(group_ids), Group.status == True)
    )
    groups = result.scalars().all()

    response = []
    for group in groups:
        # 获取成员数量
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.join_status == "active"
            )
        )
        members = result.scalars().all()

        # 获取空间ID
        result = await db.execute(
            select(Space).where(Space.group_id == group.id)
        )
        space = result.scalar_one_or_none()

        response.append(GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            owner_id=group.owner_id,
            invite_code=group.invite_code,
            is_public_join=group.is_public_join,
            status=group.status,
            member_count=len(members),
            space_id=space.id if space else None
        ))

    return response


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取群组详情"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查是否是成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 获取成员数量
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()

    # 获取空间ID
    result = await db.execute(
        select(Space).where(Space.group_id == group.id)
    )
    space = result.scalar_one_or_none()

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        invite_code=group.invite_code,
        is_public_join=group.is_public_join,
        status=group.status,
        member_count=len(members),
        space_id=space.id if space else None
    )


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新群组信息"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限（群主或管理员可修改）
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权修改群组信息")

    # 更新信息
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.is_public_join is not None:
        group.is_public_join = data.is_public_join
        # 如果开启公开加入，确保有邀请码
        if data.is_public_join and not group.invite_code:
            group.invite_code = generate_invite_code()

    await db.commit()
    await log_audit(db, current_user, "group_update", "group", group.id, f"更新群组: {group.name}", request)

    # 获取成员数量
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()

    # 获取空间ID
    result = await db.execute(
        select(Space).where(Space.group_id == group.id)
    )
    space = result.scalar_one_or_none()

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        invite_code=group.invite_code,
        is_public_join=group.is_public_join,
        status=group.status,
        member_count=len(members),
        space_id=space.id if space else None
    )


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解散群组"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 只有群主可以解散群组
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以解散群组")

    group_name = group.name

    # 删除群组空间
    result = await db.execute(
        select(Space).where(Space.group_id == group_id)
    )
    space = result.scalar_one_or_none()
    if space:
        await db.delete(space)

    # 删除成员记录
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = result.scalars().all()
    for member in members:
        await db.delete(member)

    # 删除群组
    await db.delete(group)
    await db.commit()

    await log_audit(db, current_user, "group_delete", "group", group_id, f"解散群组: {group_name}", request)

    return {"message": "群组已解散"}


@router.get("/{group_id}/members", response_model=List[MemberResponse])
async def get_group_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取群组成员列表"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查是否是成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 获取所有成员
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = result.scalars().all()

    # 获取用户信息
    response = []
    for member in members:
        result = await db.execute(
            select(User).where(User.id == member.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            response.append(MemberResponse(
                id=member.id,
                user_id=user.id,
                username=user.username,
                real_name=user.real_name,
                role=member.role,
                join_status=member.join_status,
                joined_at=member.joined_at.isoformat() if member.joined_at else ""
            ))

    return response


@router.patch("/{group_id}/members/{user_id}/role")
async def update_member_role(
    group_id: int,
    user_id: int,
    role: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改成员角色"""
    if role not in ["manager", "member", "viewer"]:
        raise HTTPException(status_code=400, detail="无效的角色")

    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限（群主或管理员可修改）
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    operator = result.scalar_one_or_none()
    if not operator or operator.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权修改成员角色")

    # 不能修改群主角色
    if user_id == group.owner_id:
        raise HTTPException(status_code=400, detail="不能修改群主角色")

    # 获取目标成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    member.role = role
    await db.commit()

    await log_audit(db, current_user, "member_role_update", "group", group_id, f"修改成员角色为: {role}", request)

    return {"message": "角色已更新"}


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退出群组"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 群主不能退出
    if group.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="群主不能退出群组，请先转让群主或解散群组")

    # 获取成员记录
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="您不是该群组成员")

    member.join_status = "left"
    await db.commit()

    await log_audit(db, current_user, "group_leave", "group", group_id, f"退出群组: {group.name}", request)

    return {"message": "已退出群组"}


@router.post("/{group_id}/kick/{user_id}")
async def kick_member(
    group_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """踢出成员"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限（群主或管理员可踢人）
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    operator = result.scalar_one_or_none()
    if not operator or operator.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权踢出成员")

    # 不能踢群主
    if user_id == group.owner_id:
        raise HTTPException(status_code=400, detail="不能踢出群主")

    # 获取目标成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    member.join_status = "left"
    await db.commit()

    await log_audit(db, current_user, "member_kick", "group", group_id, f"踢出成员", request)

    return {"message": "已踢出成员"}


@router.get("/info/{invite_code}")
async def get_group_by_invite_code(
    invite_code: str,
    db: AsyncSession = Depends(get_db),
):
    """通过邀请码获取群组信息（无需登录）"""
    result = await db.execute(
        select(Group).where(Group.invite_code == invite_code, Group.status == True)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="无效的邀请码")

    # 获取成员数量
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()

    # 获取群主信息
    result = await db.execute(
        select(User).where(User.id == group.owner_id)
    )
    owner = result.scalar_one_or_none()

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "member_count": len(members),
        "owner_name": owner.real_name or owner.username if owner else "未知",
        "invite_code": group.invite_code
    }


@router.post("/join/{invite_code}")
async def join_group_by_code(
    invite_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通过邀请码加入群组"""
    result = await db.execute(
        select(Group).where(Group.invite_code == invite_code, Group.status == True)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="无效的邀请码")

    # 检查是否已经是成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == current_user.id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.join_status == "active":
            raise HTTPException(status_code=400, detail="您已经是群组成员")
        else:
            # 重新加入
            existing.join_status = "active"
            existing.role = "member"
            await db.commit()
            return {"message": "已重新加入群组", "group_id": group.id}

    # 创建成员记录
    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="member",
        join_status="active"
    )
    db.add(member)
    await db.commit()

    await log_audit(db, current_user, "group_join", "group", group.id, f"加入群组: {group.name}", request)

    return {"message": "已加入群组", "group_id": group.id}


@router.post("/{group_id}/invite/{user_id}")
async def invite_user_to_group(
    group_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """邀请用户加入群组（需要对方同意）"""
    from app.models.models import Friendship, Invitation, Notification
    from sqlalchemy import or_, and_
    from app.core.notifications import manager

    # 检查群组是否存在
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.status == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查当前用户是否是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员，无法邀请他人")

    # 检查被邀请用户是否存在
    result = await db.execute(
        select(User).where(User.id == user_id, User.status == True)
    )
    invited_user = result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否是好友
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == user_id),
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == current_user.id)
            ),
            Friendship.status == "accepted"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="只能邀请好友加入群组")

    # 检查被邀请用户是否已经是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    existing_member = result.scalar_one_or_none()
    if existing_member and existing_member.join_status == "active":
        raise HTTPException(status_code=400, detail="该用户已经是群组成员")

    # 检查是否已有待处理的邀请
    result = await db.execute(
        select(Invitation).where(
            Invitation.group_id == group_id,
            Invitation.invitee_id == user_id,
            Invitation.status == "pending"
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该用户已有待处理的邀请")

    # 创建邀请记录
    invitation = Invitation(
        group_id=group_id,
        inviter_id=current_user.id,
        invitee_id=user_id,
        status="pending"
    )
    db.add(invitation)
    await db.flush()  # 获取invitation.id
    await db.refresh(invitation)

    # 创建或更新成员记录（状态为invited）
    if existing_member:
        existing_member.join_status = "invited"
        existing_member.invited_by = current_user.id
    else:
        member = GroupMember(
            group_id=group_id,
            user_id=user_id,
            role="member",
            join_status="invited",
            invited_by=current_user.id
        )
        db.add(member)

    # 创建通知记录
    notification = Notification(
        user_id=user_id,
        notification_type="group_invite",
        title="群组邀请",
        content=f"{current_user.real_name or current_user.username} 邀请您加入群组「{group.name}」",
        data={
            "group_id": group.id,
            "group_name": group.name,
            "inviter_id": current_user.id,
            "inviter_name": current_user.real_name or current_user.username,
            "invitation_id": invitation.id
        },
        related_id=invitation.id,
        related_type="invitation"
    )
    db.add(notification)
    await db.commit()
    await db.refresh(invitation)

    # 实时推送通知给被邀请用户
    await manager.send_personal_message({
        "type": "group_invite",
        "data": {
            "notification_id": notification.id,
            "invitation_id": invitation.id,
            "group_id": group.id,
            "group_name": group.name,
            "inviter_id": current_user.id,
            "inviter_name": current_user.real_name or current_user.username
        }
    }, user_id)

    await log_audit(db, current_user, "group_invite", "group", group_id, f"邀请用户加入群组", request)

    return {"message": "邀请已发送，等待对方确认", "group_id": group.id, "invitation_id": invitation.id}


@router.get("/{group_id}/invite-friends")
async def get_friends_not_in_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取不在群组中的好友列表（用于邀请）"""
    from app.models.models import Friendship
    from sqlalchemy import or_, and_

    # 检查群组是否存在
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.status == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查当前用户是否是群组成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该群组成员")

    # 获取好友列表
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

    friend_ids = []
    for f in friendships:
        if f.requester_id == current_user.id:
            friend_ids.append(f.addressee_id)
        else:
            friend_ids.append(f.requester_id)

    if not friend_ids:
        return []

    # 获取已在群组中的成员ID
    result = await db.execute(
        select(GroupMember.user_id).where(
            GroupMember.group_id == group_id,
            GroupMember.join_status == "active"
        )
    )
    member_ids = [m[0] for m in result.fetchall()]

    # 获取不在群组中的好友
    result = await db.execute(
        select(User).where(
            User.id.in_(friend_ids),
            User.status == True
        )
    )
    friends = result.scalars().all()

    response = []
    for friend in friends:
        if friend.id not in member_ids:
            response.append({
                "id": friend.id,
                "username": friend.username,
                "real_name": friend.real_name
            })

    return response


@router.post("/invitation/{invitation_id}/accept")
async def accept_group_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接受群组邀请"""
    from app.models.models import Invitation, Notification
    from app.core.notifications import manager

    # 获取邀请记录
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.invitee_id == current_user.id,
            Invitation.status == "pending"
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在或已处理")

    # 获取群组信息
    result = await db.execute(select(Group).where(Group.id == invitation.group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 更新邀请状态
    invitation.status = "accepted"

    # 更新成员状态
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == invitation.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    member = result.scalar_one_or_none()
    if member:
        member.join_status = "active"
    else:
        member = GroupMember(
            group_id=invitation.group_id,
            user_id=current_user.id,
            role="member",
            join_status="active",
            invited_by=invitation.inviter_id
        )
        db.add(member)

    # 标记相关通知为已读
    result = await db.execute(
        select(Notification).where(
            Notification.related_id == invitation_id,
            Notification.related_type == "invitation",
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.is_read = True

    await db.commit()

    # 通知邀请人
    await manager.send_personal_message({
        "type": "group_invite_accepted",
        "data": {
            "group_id": group.id,
            "group_name": group.name,
            "user_id": current_user.id,
            "user_name": current_user.real_name or current_user.username
        }
    }, invitation.inviter_id)

    # 通知被邀请人
    await manager.send_personal_message({
        "type": "group_joined",
        "data": {
            "group_id": group.id,
            "group_name": group.name
        }
    }, current_user.id)

    return {"message": f"已加入群组「{group.name}」", "group_id": group.id}


@router.post("/invitation/{invitation_id}/reject")
async def reject_group_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """拒绝群组邀请"""
    from app.models.models import Invitation, Notification
    from app.core.notifications import manager

    # 获取邀请记录
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.invitee_id == current_user.id,
            Invitation.status == "pending"
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在或已处理")

    # 获取群组信息
    result = await db.execute(select(Group).where(Group.id == invitation.group_id))
    group = result.scalar_one_or_none()

    # 更新邀请状态
    invitation.status = "rejected"

    # 更新成员状态
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == invitation.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    member = result.scalar_one_or_none()
    if member:
        member.join_status = "rejected"

    # 标记相关通知为已读
    result = await db.execute(
        select(Notification).where(
            Notification.related_id == invitation_id,
            Notification.related_type == "invitation",
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.is_read = True

    await db.commit()

    # 通知邀请人
    if group:
        await manager.send_personal_message({
            "type": "group_invite_rejected",
            "data": {
                "group_id": group.id,
                "group_name": group.name,
                "user_id": current_user.id,
                "user_name": current_user.real_name or current_user.username
            }
        }, invitation.inviter_id)

    return {"message": "已拒绝邀请"}
