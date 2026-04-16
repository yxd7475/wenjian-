"""
邀请管理 API
"""
import secrets
from datetime import timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import User, Group, GroupMember, Invitation
from app.api.deps import get_current_user
from app.api.files import log_audit
from app.utils.timezone import get_beijing_time
from app.core.notifications import notify_invitation, notify_invitation_accepted, notify_group_member

router = APIRouter(prefix="/invitations", tags=["邀请管理"])


class InvitationCreate(BaseModel):
    group_id: int
    invitee_id: Optional[int] = None  # 如果为空，则生成通用邀请链接
    invitee_ids: Optional[List[int]] = None  # 批量邀请多个用户
    expire_days: Optional[int] = 7  # 邀请有效期（天）


class InvitationResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    inviter_id: int
    inviter_name: str
    invitee_id: Optional[int]
    invitee_name: Optional[str]
    invite_code: Optional[str]
    invite_link: Optional[str] = None  # 完整邀请链接
    status: str
    expire_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class BatchInvitationResponse(BaseModel):
    success_count: int
    failed_count: int
    invitations: List[InvitationResponse]
    failed_users: List[dict]


def generate_invite_code():
    """生成邀请码"""
    return secrets.token_urlsafe(8)


@router.post("", response_model=InvitationResponse)
async def create_invitation(
    data: InvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送邀请 - 支持单个用户邀请或生成邀请链接"""
    # 检查群组是否存在
    result = await db.execute(
        select(Group).where(Group.id == data.group_id, Group.status == True)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限（群主或管理员可邀请）
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == data.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权邀请成员")

    invite_code = generate_invite_code()
    expire_at = get_beijing_time() + timedelta(days=data.expire_days or 7)

    # 如果指定了被邀请人
    if data.invitee_id:
        result = await db.execute(
            select(User).where(User.id == data.invitee_id, User.status == True)
        )
        invitee = result.scalar_one_or_none()
        if not invitee:
            raise HTTPException(status_code=404, detail="被邀请用户不存在")

        # 检查是否已经是成员
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == data.group_id,
                GroupMember.user_id == data.invitee_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing and existing.join_status == "active":
            raise HTTPException(status_code=400, detail="该用户已经是群组成员")

        invitation = Invitation(
            group_id=data.group_id,
            inviter_id=current_user.id,
            invitee_id=data.invitee_id,
            invite_code=invite_code,
            status="pending",
            expire_at=expire_at
        )
    else:
        # 生成通用邀请链接
        invitation = Invitation(
            group_id=data.group_id,
            inviter_id=current_user.id,
            invitee_id=None,
            invite_code=invite_code,
            status="pending",
            expire_at=expire_at
        )

    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    # 发送实时通知给被邀请人
    if data.invitee_id:
        await notify_invitation(data.invitee_id, {
            "id": invitation.id,
            "group_id": group.id,
            "group_name": group.name,
            "inviter_name": current_user.username,
            "invite_code": invite_code,
            "expire_at": expire_at.isoformat()
        })

    await log_audit(db, current_user, "invitation_create", "group", data.group_id, f"创建邀请", request)

    # 构建响应
    result = await db.execute(select(User).where(User.id == current_user.id))
    inviter = result.scalar_one()

    invitee_name = None
    if data.invitee_id:
        result = await db.execute(select(User).where(User.id == data.invitee_id))
        invitee = result.scalar_one_or_none()
        invitee_name = invitee.username if invitee else None

    # 构建邀请链接
    base_url = str(request.base_url).rstrip('/')
    invite_link = f"{base_url}/join/{invite_code}"

    return InvitationResponse(
        id=invitation.id,
        group_id=group.id,
        group_name=group.name,
        inviter_id=current_user.id,
        inviter_name=inviter.username,
        invitee_id=data.invitee_id,
        invitee_name=invitee_name,
        invite_code=invite_code,
        invite_link=invite_link,
        status=invitation.status,
        expire_at=expire_at.isoformat(),
        created_at=invitation.created_at.isoformat()
    )


@router.post("/batch", response_model=BatchInvitationResponse)
async def batch_invite_users(
    data: InvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量邀请多个用户"""
    if not data.invitee_ids:
        raise HTTPException(status_code=400, detail="请选择要邀请的用户")

    # 检查群组是否存在
    result = await db.execute(
        select(Group).where(Group.id == data.group_id, Group.status == True)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == data.group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权邀请成员")

    expire_at = get_beijing_time() + timedelta(days=data.expire_days or 7)
    invitations = []
    failed_users = []

    for user_id in data.invitee_ids:
        try:
            # 检查用户是否存在
            result = await db.execute(
                select(User).where(User.id == user_id, User.status == True)
            )
            invitee = result.scalar_one_or_none()
            if not invitee:
                failed_users.append({"user_id": user_id, "reason": "用户不存在"})
                continue

            # 检查是否已经是成员
            result = await db.execute(
                select(GroupMember).where(
                    GroupMember.group_id == data.group_id,
                    GroupMember.user_id == user_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing and existing.join_status == "active":
                failed_users.append({"user_id": user_id, "username": invitee.username, "reason": "已是群组成员"})
                continue

            # 检查是否已有待处理的邀请
            result = await db.execute(
                select(Invitation).where(
                    Invitation.group_id == data.group_id,
                    Invitation.invitee_id == user_id,
                    Invitation.status == "pending"
                )
            )
            existing_inv = result.scalar_one_or_none()
            if existing_inv:
                failed_users.append({"user_id": user_id, "username": invitee.username, "reason": "已有待处理的邀请"})
                continue

            # 创建邀请
            invite_code = generate_invite_code()
            invitation = Invitation(
                group_id=data.group_id,
                inviter_id=current_user.id,
                invitee_id=user_id,
                invite_code=invite_code,
                status="pending",
                expire_at=expire_at
            )
            db.add(invitation)

            # 发送通知
            await notify_invitation(user_id, {
                "id": 0,  # 临时ID，commit后会有真实ID
                "group_id": group.id,
                "group_name": group.name,
                "inviter_name": current_user.username,
                "invite_code": invite_code,
                "expire_at": expire_at.isoformat()
            })

            invitations.append({
                "user_id": user_id,
                "username": invitee.username,
                "invite_code": invite_code
            })

        except Exception as e:
            failed_users.append({"user_id": user_id, "reason": str(e)})

    await db.commit()
    await log_audit(db, current_user, "invitation_batch", "group", data.group_id,
                   f"批量邀请 {len(invitations)} 人", request)

    return BatchInvitationResponse(
        success_count=len(invitations),
        failed_count=len(failed_users),
        invitations=[InvitationResponse(
            id=0,
            group_id=group.id,
            group_name=group.name,
            inviter_id=current_user.id,
            inviter_name=current_user.username,
            invitee_id=inv["user_id"],
            invitee_name=inv["username"],
            invite_code=inv["invite_code"],
            invite_link=f"{str(request.base_url).rstrip('/')}/join/{inv['invite_code']}",
            status="pending",
            expire_at=expire_at.isoformat(),
            created_at=get_beijing_time().isoformat()
        ) for inv in invitations],
        failed_users=failed_users
    )


@router.get("/link/{group_id}")
async def get_invite_link(
    group_id: int,
    request: Request,
    expire_days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取群组邀请链接"""
    # 检查群组
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.status == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查权限
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in ["owner", "manager"]:
        raise HTTPException(status_code=403, detail="无权生成邀请链接")

    # 使用群组的邀请码，如果没有则生成
    if not group.invite_code:
        group.invite_code = generate_invite_code()
        await db.commit()

    expire_at = get_beijing_time() + timedelta(days=expire_days)
    base_url = str(request.base_url).rstrip('/')

    return {
        "group_id": group.id,
        "group_name": group.name,
        "invite_code": group.invite_code,
        "invite_link": f"{base_url}/join/{group.invite_code}",
        "qr_code_url": f"{base_url}/api/invitations/qrcode/{group.invite_code}",
        "expire_days": expire_days,
        "expire_at": expire_at.isoformat()
    }


@router.get("", response_model=List[InvitationResponse])
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我的邀请列表"""
    # 获取发给当前用户的邀请
    result = await db.execute(
        select(Invitation).where(
            Invitation.invitee_id == current_user.id,
            Invitation.status == "pending"
        ).order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()

    # 检查过期
    response = []
    for inv in invitations:
        if inv.expire_at and inv.expire_at < get_beijing_time():
            inv.status = "expired"
            await db.commit()
            continue

        result = await db.execute(select(Group).where(Group.id == inv.group_id))
        group = result.scalar_one_or_none()
        if not group:
            continue

        result = await db.execute(select(User).where(User.id == inv.inviter_id))
        inviter = result.scalar_one_or_none()
        if not inviter:
            continue

        response.append(InvitationResponse(
            id=inv.id,
            group_id=group.id,
            group_name=group.name,
            inviter_id=inv.inviter_id,
            inviter_name=inviter.username,
            invitee_id=inv.invitee_id,
            invitee_name=current_user.username,
            invite_code=inv.invite_code,
            status=inv.status,
            expire_at=inv.expire_at.isoformat() if inv.expire_at else None,
            created_at=inv.created_at.isoformat()
        ))

    return response


@router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接受邀请"""
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")

    if invitation.invitee_id and invitation.invitee_id != current_user.id:
        raise HTTPException(status_code=403, detail="这不是发给您的邀请")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="邀请已处理")

    if invitation.expire_at and invitation.expire_at < get_beijing_time():
        invitation.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="邀请已过期")

    # 检查群组
    result = await db.execute(select(Group).where(Group.id == invitation.group_id))
    group = result.scalar_one_or_none()
    if not group or not group.status:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 检查是否已经是成员
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == invitation.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.join_status == "active":
            raise HTTPException(status_code=400, detail="您已经是群组成员")
        existing.join_status = "active"
        existing.role = "member"
        existing.joined_at = get_beijing_time()
    else:
        # 创建成员记录
        member = GroupMember(
            group_id=invitation.group_id,
            user_id=current_user.id,
            role="member",
            join_status="active",
            invited_by=invitation.inviter_id
        )
        db.add(member)

    invitation.status = "accepted"
    await db.commit()

    # 发送实时通知
    # 1. 通知邀请人
    await notify_invitation_accepted(invitation.inviter_id, {
        "group_id": group.id,
        "group_name": group.name,
        "new_member_name": current_user.real_name or current_user.username
    })

    # 2. 通知其他群组成员有新成员加入
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == invitation.group_id,
            GroupMember.join_status == "active"
        )
    )
    members = result.scalars().all()
    member_ids = [m.user_id for m in members if m.user_id != current_user.id]

    await notify_group_member(
        invitation.group_id,
        {
            "user_id": current_user.id,
            "username": current_user.username,
            "real_name": current_user.real_name
        },
        member_ids
    )

    await log_audit(db, current_user, "invitation_accept", "group", invitation.group_id, f"接受邀请加入群组", request)

    return {"message": "已加入群组", "group_id": invitation.group_id}


@router.post("/{invitation_id}/reject")
async def reject_invitation(
    invitation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """拒绝邀请"""
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")

    if invitation.invitee_id and invitation.invitee_id != current_user.id:
        raise HTTPException(status_code=403, detail="这不是发给您的邀请")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="邀请已处理")

    invitation.status = "rejected"
    await db.commit()

    await log_audit(db, current_user, "invitation_reject", "group", invitation.group_id, f"拒绝邀请", request)

    return {"message": "已拒绝邀请"}


@router.get("/my-sent")
async def list_sent_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我发出的邀请"""
    result = await db.execute(
        select(Invitation).where(
            Invitation.inviter_id == current_user.id
        ).order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()

    response = []
    for inv in invitations:
        result = await db.execute(select(Group).where(Group.id == inv.group_id))
        group = result.scalar_one_or_none()

        invitee_name = None
        if inv.invitee_id:
            result = await db.execute(select(User).where(User.id == inv.invitee_id))
            invitee = result.scalar_one_or_none()
            invitee_name = invitee.username if invitee else None

        response.append({
            "id": inv.id,
            "group_id": inv.group_id,
            "group_name": group.name if group else "未知群组",
            "invitee_id": inv.invitee_id,
            "invitee_name": invitee_name,
            "invite_code": inv.invite_code,
            "status": inv.status,
            "expire_at": inv.expire_at.isoformat() if inv.expire_at else None,
            "created_at": inv.created_at.isoformat()
        })

    return response
