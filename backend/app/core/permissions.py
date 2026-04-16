"""
空间权限管理
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import User, Space, GroupMember


async def check_space_access(
    db: AsyncSession,
    space: Space,
    user: User
) -> bool:
    """
    检查用户是否有空间访问权限
    返回 True 表示有权限，False 表示无权限
    """
    if space.space_type == "admin":
        # 管理员空间：仅超级管理员和管理员可见
        if user.is_superuser:
            return True
        if user.role and user.role.code in ["super_admin", "admin"]:
            return True
        return False

    elif space.space_type == "personal":
        # 个人空间：仅本人可见
        if space.owner_id == user.id:
            return True
        return False

    elif space.space_type == "group":
        # 群组空间：群组成员可见
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == space.group_id,
                GroupMember.user_id == user.id,
                GroupMember.join_status == "active"
            )
        )
        if result.scalar_one_or_none():
            return True
        return False

    return False


async def get_space_role(
    db: AsyncSession,
    space: Space,
    user: User
) -> str:
    """
    获取用户在空间中的角色
    返回: owner/manager/member/viewer/none
    """
    if space.space_type == "admin":
        if user.is_superuser or (user.role and user.role.code == "super_admin"):
            return "owner"
        elif user.role and user.role.code == "admin":
            return "manager"
        return "none"

    elif space.space_type == "personal":
        if space.owner_id == user.id:
            return "owner"
        return "none"

    elif space.space_type == "group":
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == space.group_id,
                GroupMember.user_id == user.id,
                GroupMember.join_status == "active"
            )
        )
        member = result.scalar_one_or_none()
        if member:
            return member.role
        return "none"

    return "none"


def can_upload(role: str) -> bool:
    """检查角色是否可以上传文件"""
    return role in ["owner", "manager", "member"]


def can_delete(role: str, file_owner_id: int, user_id: int) -> bool:
    """检查角色是否可以删除文件"""
    if role in ["owner", "manager"]:
        return True
    if role == "member" and file_owner_id == user_id:
        return True
    return False


def can_manage_members(role: str) -> bool:
    """检查角色是否可以管理成员"""
    return role in ["owner", "manager"]


def can_create_folder(role: str) -> bool:
    """检查角色是否可以创建文件夹"""
    return role in ["owner", "manager", "member"]


def can_rename(role: str) -> bool:
    """检查角色是否可以重命名"""
    return role in ["owner", "manager", "member"]


def can_download(role: str) -> bool:
    """检查角色是否可以下载"""
    return role in ["owner", "manager", "member", "viewer"]
