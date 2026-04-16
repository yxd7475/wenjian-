"""
空间管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import User, Space, Group, GroupMember, Folder
from app.api.deps import get_current_user

router = APIRouter(prefix="/spaces", tags=["空间管理"])


class SpaceResponse(BaseModel):
    id: int
    name: str
    space_type: str
    owner_id: Optional[int]
    group_id: Optional[int]
    description: Optional[str]
    status: bool

    class Config:
        from_attributes = True


class SpaceDetailResponse(SpaceResponse):
    root_folder_id: Optional[int]
    file_count: int = 0
    total_size: int = 0


@router.get("", response_model=List[SpaceResponse])
async def list_spaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户可见的所有空间"""
    spaces = []

    # 1. 管理员空间 - 仅管理员可见
    if current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"]):
        result = await db.execute(
            select(Space).where(Space.space_type == "admin", Space.status == True)
        )
        admin_spaces = result.scalars().all()
        spaces.extend(admin_spaces)

    # 2. 个人空间 - 仅本人可见
    result = await db.execute(
        select(Space).where(
            Space.space_type == "personal",
            Space.owner_id == current_user.id,
            Space.status == True
        )
    )
    personal_spaces = result.scalars().all()
    spaces.extend(personal_spaces)

    # 3. 群组空间 - 群组成员可见
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.user_id == current_user.id,
            GroupMember.join_status == "active"
        )
    )
    memberships = result.scalars().all()
    group_ids = [m.group_id for m in memberships]

    if group_ids:
        result = await db.execute(
            select(Space).where(
                Space.space_type == "group",
                Space.group_id.in_(group_ids),
                Space.status == True
            )
        )
        group_spaces = result.scalars().all()
        spaces.extend(group_spaces)

    return spaces


@router.get("/{space_id}", response_model=SpaceDetailResponse)
async def get_space(
    space_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取空间详情"""
    result = await db.execute(
        select(Space).where(Space.id == space_id)
    )
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    # 权限检查
    await check_space_access(space, current_user, db)

    # 获取根文件夹
    result = await db.execute(
        select(Folder).where(
            Folder.space_id == space_id,
            Folder.parent_id == None,
            Folder.is_deleted == False
        )
    )
    root_folder = result.scalar_one_or_none()

    # 统计文件数量和大小
    from app.models.models import File
    result = await db.execute(
        select(File).where(
            File.space_id == space_id,
            File.is_deleted == False,
            File.status == 1
        )
    )
    files = result.scalars().all()
    file_count = len(files)
    total_size = sum(f.size for f in files)

    return SpaceDetailResponse(
        id=space.id,
        name=space.name,
        space_type=space.space_type,
        owner_id=space.owner_id,
        group_id=space.group_id,
        description=space.description,
        status=space.status,
        root_folder_id=root_folder.id if root_folder else None,
        file_count=file_count,
        total_size=total_size
    )


@router.get("/{space_id}/folders")
async def get_space_folders(
    space_id: int,
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取空间文件夹列表"""
    result = await db.execute(
        select(Space).where(Space.id == space_id)
    )
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    # 权限检查
    await check_space_access(space, current_user, db)

    # 获取文件夹列表
    if parent_id:
        result = await db.execute(
            select(Folder).where(
                Folder.space_id == space_id,
                Folder.parent_id == parent_id,
                Folder.is_deleted == False
            ).order_by(Folder.name)
        )
    else:
        # 获取根文件夹
        result = await db.execute(
            select(Folder).where(
                Folder.space_id == space_id,
                Folder.parent_id == None,
                Folder.is_deleted == False
            ).order_by(Folder.name)
        )

    folders = result.scalars().all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "parent_id": f.parent_id,
            "has_children": len(f.children) > 0 if f.children else False
        }
        for f in folders
    ]


@router.get("/{space_id}/root-folder")
async def get_or_create_root_folder(
    space_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取或创建空间根文件夹"""
    result = await db.execute(
        select(Space).where(Space.id == space_id)
    )
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    # 权限检查
    await check_space_access(space, current_user, db)

    # 查找根文件夹
    result = await db.execute(
        select(Folder).where(
            Folder.space_id == space_id,
            Folder.parent_id == None,
            Folder.is_deleted == False
        )
    )
    root_folder = result.scalar_one_or_none()

    if not root_folder:
        # 创建根文件夹
        root_folder = Folder(
            space_id=space_id,
            parent_id=None,
            name="根目录",
            path="/",
            owner_id=current_user.id,
            is_deleted=False
        )
        db.add(root_folder)
        await db.commit()
        await db.refresh(root_folder)

    return {
        "id": root_folder.id,
        "name": root_folder.name,
        "path": root_folder.path
    }


async def check_space_access(space: Space, user: User, db: AsyncSession) -> bool:
    """检查用户是否有空间访问权限"""
    if space.space_type == "admin":
        # 管理员空间：仅超级管理员和管理员可见
        if not (user.is_superuser or (user.role and user.role.code in ["super_admin", "admin"])):
            raise HTTPException(status_code=403, detail="无权访问此空间")

    elif space.space_type == "personal":
        # 个人空间：仅本人可见
        if space.owner_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此空间")

    elif space.space_type == "group":
        # 群组空间：群组成员可见
        result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == space.group_id,
                GroupMember.user_id == user.id,
                GroupMember.join_status == "active"
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="无权访问此空间")

    return True


async def get_user_space_role(space: Space, user: User, db: AsyncSession) -> str:
    """获取用户在空间中的角色"""
    if space.space_type == "admin":
        if user.is_superuser or (user.role and user.role.code == "super_admin"):
            return "owner"
        elif user.role and user.role.code == "admin":
            return "manager"
        return "viewer"

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
