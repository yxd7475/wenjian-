"""
文件分类管理 API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import User, FileCategory
from app.api.deps import get_current_user

router = APIRouter(prefix="/categories", tags=["文件分类"])


class CategoryCreate(BaseModel):
    name: str
    icon: str = "Document"
    color: str = "#409EFF"
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str = None
    icon: str = None
    color: str = None
    sort_order: int = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    icon: str = None
    color: str = None
    sort_order: int = 0

    class Config:
        from_attributes = True


@router.get("", response_model=List[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有文件分类"""
    result = await db.execute(
        select(FileCategory).order_by(FileCategory.sort_order)
    )
    categories = result.scalars().all()
    return categories


@router.post("", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建文件分类（仅管理员）"""
    if not (current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"])):
        raise HTTPException(status_code=403, detail="无权限创建分类")

    # 检查名称是否已存在
    result = await db.execute(
        select(FileCategory).where(FileCategory.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="分类名称已存在")

    category = FileCategory(
        name=data.name,
        icon=data.icon,
        color=data.color,
        sort_order=data.sort_order,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新文件分类（仅管理员）"""
    if not (current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"])):
        raise HTTPException(status_code=403, detail="无权限更新分类")

    result = await db.execute(
        select(FileCategory).where(FileCategory.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    if data.name is not None:
        # 检查名称是否与其他分类重复
        result = await db.execute(
            select(FileCategory).where(
                FileCategory.name == data.name,
                FileCategory.id != category_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="分类名称已存在")
        category.name = data.name

    if data.icon is not None:
        category.icon = data.icon
    if data.color is not None:
        category.color = data.color
    if data.sort_order is not None:
        category.sort_order = data.sort_order

    await db.commit()
    await db.refresh(category)

    return category


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除文件分类（仅管理员）"""
    if not (current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"])):
        raise HTTPException(status_code=403, detail="无权限删除分类")

    result = await db.execute(
        select(FileCategory).where(FileCategory.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    await db.delete(category)
    await db.commit()

    return {"message": "分类已删除"}
