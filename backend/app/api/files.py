"""
文件管理 API 路由
"""
import os
import uuid
import hashlib
import aiofiles
import zipfile
import tempfile
import chardet
from urllib.parse import quote
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File as FastAPIFile, Form, Body
from fastapi.responses import StreamingResponse, FileResponse as FastAPIFileResponse, Response
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.models import User, File as FileModel, Folder, AuditLog, UploadTask, Permission, RolePermission, FileVersion, Space, GroupMember
from app.utils.timezone import get_beijing_time
from app.schemas import (
    FileResponse,
    FileListResponse,
    FolderCreate,
    FolderRename,
    FolderResponse,
    FolderTree,
    FileMove,
    FileCopy,
    UploadInit,
    UploadComplete,
    UploadTaskResponse,
    MessageResponse,
)
from app.core.config import settings
from app.api.deps import get_current_user, require_permission, get_superuser
from app.core.notifications import notify_new_file, notify_file_deleted

router = APIRouter(prefix="/files", tags=["文件管理"])


def get_file_hash(file_path: str) -> str:
    """计算文件SHA256哈希"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


async def stream_file_to_disk(upload_file: UploadFile, storage_path: str, chunk_size: int = 1024 * 1024):
    """流式写入文件到磁盘并计算SHA256，返回 (file_size, sha256_hash)"""
    sha256_hash = hashlib.sha256()
    total_size = 0
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    async with aiofiles.open(storage_path, "wb") as f:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)
            await f.write(chunk)
            total_size += len(chunk)
    return total_size, sha256_hash.hexdigest()


async def log_audit(
    db: AsyncSession,
    user: User,
    action: str,
    target_type: str,
    target_id: int,
    target_name: str,
    request: Request,
    result: bool = True,
    detail: dict = None,
):
    """记录审计日志"""
    log = AuditLog(
        user_id=user.id,
        username=user.username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
        result=result,
        detail=detail,
    )
    db.add(log)
    await db.commit()


# ==================== 文件夹管理 ====================

@router.get("/folders/tree", response_model=List[FolderTree])
async def get_folder_tree(
    space_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文件夹树"""
    from app.api.spaces import check_space_access

    visible_space_ids = []

    # 如果指定了 space_id，验证权限并只返回该空间的文件夹
    if space_id:
        result = await db.execute(
            select(Space).where(Space.id == space_id)
        )
        space = result.scalar_one_or_none()
        if space:
            await check_space_access(space, current_user, db)
        visible_space_ids = [space_id]
    else:
        # 如果没有指定空间，默认只返回个人空间的文件夹
        result = await db.execute(
            select(Space).where(
                Space.space_type == "personal",
                Space.owner_id == current_user.id,
                Space.status == True
            )
        )
        personal_space = result.scalar_one_or_none()
        if personal_space:
            visible_space_ids = [personal_space.id]
        else:
            return []

    # 查询文件夹
    query = select(Folder).where(
        Folder.is_deleted == False,
        Folder.space_id.in_(visible_space_ids)
    ).order_by(Folder.name)

    result = await db.execute(query)
    folders = result.scalars().all()

    # 构建树形结构
    folder_map = {
        f.id: FolderTree(
            id=f.id,
            name=f.name,
            parent_id=f.parent_id,
            space_id=f.space_id,
            path=f.path,
            owner_id=f.owner_id,
            is_deleted=f.is_deleted,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in folders
    }
    root_folders = []

    for folder in folders:
        folder_tree = folder_map[folder.id]
        if folder.parent_id is None:
            root_folders.append(folder_tree)
        elif folder.parent_id in folder_map:
            parent = folder_map[folder.parent_id]
            if parent.children is None:
                parent.children = []
            parent.children.append(folder_tree)

    return root_folders


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    data: FolderCreate,
    request: Request,
    current_user: User = Depends(require_permission("folder:create")),
    db: AsyncSession = Depends(get_db),
):
    """创建文件夹"""
    # 获取 space_id（从父文件夹继承或从请求参数）
    space_id = getattr(data, 'space_id', None)

    # 检查父文件夹是否存在
    if data.parent_id:
        result = await db.execute(
            select(Folder).where(Folder.id == data.parent_id, Folder.is_deleted == False)
        )
        parent_folder = result.scalar_one_or_none()
        if not parent_folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父文件夹不存在",
            )
        space_id = parent_folder.space_id

    # 如果没有 space_id，获取用户的个人空间
    if not space_id:
        result = await db.execute(
            select(Space).where(Space.space_type == "personal", Space.owner_id == current_user.id)
        )
        personal_space = result.scalar_one_or_none()
        if personal_space:
            space_id = personal_space.id

    # 检查同名文件夹
    query = select(Folder).where(
        Folder.name == data.name,
        Folder.is_deleted == False,
        Folder.space_id == space_id
    )
    if data.parent_id:
        query = query.where(Folder.parent_id == data.parent_id)
    else:
        query = query.where(Folder.parent_id == None)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同名文件夹已存在",
        )

    # 创建文件夹
    folder = Folder(
        space_id=space_id,
        name=data.name,
        parent_id=data.parent_id,
        owner_id=current_user.id,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)

    # 更新路径
    if data.parent_id:
        parent = (await db.execute(select(Folder).where(Folder.id == data.parent_id))).scalar_one()
        folder.path = f"{parent.path}/{folder.id}"
    else:
        folder.path = f"/{folder.id}"
    await db.commit()

    # 在物理存储创建目录
    storage_path = os.path.join(settings.STORAGE_PATH, folder.path.strip("/"))
    os.makedirs(storage_path, exist_ok=True)

    await log_audit(db, current_user, "folder_create", "folder", folder.id, folder.name, request)

    return FolderResponse.model_validate(folder)


@router.put("/folders/{folder_id}", response_model=FolderResponse)
async def rename_folder(
    folder_id: int,
    data: FolderRename,
    request: Request,
    current_user: User = Depends(require_permission("folder:rename")),
    db: AsyncSession = Depends(get_db),
):
    """重命名文件夹"""
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.is_deleted == False)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在",
        )

    # 检查同名
    query = select(Folder).where(Folder.name == data.name, Folder.is_deleted == False, Folder.id != folder_id)
    if folder.parent_id:
        query = query.where(Folder.parent_id == folder.parent_id)
    else:
        query = query.where(Folder.parent_id == None)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同名文件夹已存在",
        )

    old_name = folder.name
    folder.name = data.name
    await db.commit()

    await log_audit(
        db, current_user, "folder_rename", "folder", folder.id, folder.name, request,
        detail={"old_name": old_name, "new_name": data.name}
    )

    return FolderResponse.model_validate(folder)


@router.delete("/folders/{folder_id}", response_model=MessageResponse)
async def delete_folder(
    folder_id: int,
    request: Request,
    current_user: User = Depends(require_permission("folder:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除文件夹 (软删除到回收站)"""
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.is_deleted == False)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在",
        )

    # 递归删除子文件夹和文件
    async def delete_folder_recursive(folder_id: int):
        # 删除子文件夹
        result = await db.execute(
            select(Folder).where(Folder.parent_id == folder_id, Folder.is_deleted == False)
        )
        for child in result.scalars().all():
            await delete_folder_recursive(child.id)

        # 删除文件夹内的文件
        result = await db.execute(
            select(FileModel).where(FileModel.folder_id == folder_id, FileModel.is_deleted == False)
        )
        for file in result.scalars().all():
            file.is_deleted = True
            file.status = 2

        # 删除文件夹
        folder_result = await db.execute(select(Folder).where(Folder.id == folder_id))
        f = folder_result.scalar_one()
        f.is_deleted = True

    await delete_folder_recursive(folder_id)
    await db.commit()

    await log_audit(db, current_user, "folder_delete", "folder", folder.id, folder.name, request)

    return MessageResponse(message="文件夹已移入回收站")


# ==================== 文件管理 ====================

@router.get("", response_model=FileListResponse)
async def list_files(
    folder_id: Optional[int] = None,
    space_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    ext: Optional[str] = None,
    owner_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文件列表"""
    from app.api.spaces import check_space_access

    query = select(FileModel).options(selectinload(FileModel.owner)).where(FileModel.is_deleted == False)

    # 按 space_id 过滤，并验证权限
    if space_id:
        # 验证空间访问权限
        result = await db.execute(
            select(Space).where(Space.id == space_id)
        )
        space = result.scalar_one_or_none()
        if space:
            await check_space_access(space, current_user, db)
        query = query.where(FileModel.space_id == space_id)
    else:
        # 如果没有指定空间，默认只返回个人空间的文件
        result = await db.execute(
            select(Space).where(
                Space.space_type == "personal",
                Space.owner_id == current_user.id,
                Space.status == True
            )
        )
        personal_space = result.scalar_one_or_none()

        if personal_space:
            query = query.where(FileModel.space_id == personal_space.id)
        else:
            # 用户没有个人空间，返回空结果
            return FileListResponse(items=[], total=0, page=page, page_size=page_size)

    # 按 folder_id 过滤
    if folder_id:
        query = query.where(FileModel.folder_id == folder_id)
    else:
        # 没有指定文件夹时，获取根目录文件（folder_id 为 None）
        query = query.where(FileModel.folder_id == None)

    if keyword:
        query = query.where(FileModel.origin_name.ilike(f"%{keyword}%"))
    if ext:
        query = query.where(FileModel.ext == ext.lower())
    if owner_id:
        query = query.where(FileModel.owner_id == owner_id)
    if date_from:
        query = query.where(FileModel.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(FileModel.created_at <= datetime.fromisoformat(date_to))

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(FileModel.created_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    folder_id: Optional[int] = Query(None),
    space_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    remark: Optional[str] = Form(None),
    overwrite: bool = Form(False),
    current_user: User = Depends(require_permission("file:upload")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {ext}",
        )

    origin_name = os.path.basename(file.filename)

    # 确定空间和存储路径
    folder_path = ""
    actual_space_id = space_id

    # 如果指定了空间ID，验证空间存在和权限
    if actual_space_id:
        result = await db.execute(
            select(Space).where(Space.id == actual_space_id, Space.status == True)
        )
        space = result.scalar_one_or_none()
        if not space:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="空间不存在"
            )

        # 检查空间访问权限
        if space.space_type == "personal":
            if space.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此空间"
                )
        elif space.space_type == "group":
            # 检查群组成员资格
            result = await db.execute(
                select(GroupMember).where(
                    GroupMember.group_id == space.group_id,
                    GroupMember.user_id == current_user.id,
                    GroupMember.join_status == "active"
                )
            )
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您不是该群组成员"
                )
        # admin空间只有管理员可以上传
        elif space.space_type == "admin":
            if not (current_user.is_superuser or (current_user.role and current_user.role.code in ["super_admin", "admin"])):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问管理员空间"
                )
        # 公共空间所有用户都可以上传
        elif space.space_type == "public":
            pass  # 所有登录用户都可以上传

    if folder_id:
        result = await db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.is_deleted == False)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件夹不存在",
            )
        folder_path = folder.path.strip("/") if folder.path else ""
        actual_space_id = folder.space_id

    # 如果没有指定空间，使用用户的个人空间
    if not actual_space_id:
        result = await db.execute(
            select(Space).where(Space.space_type == "personal", Space.owner_id == current_user.id)
        )
        personal_space = result.scalar_one_or_none()
        if personal_space:
            actual_space_id = personal_space.id

    # 检查重名文件
    existing_query = select(FileModel).where(
        FileModel.origin_name == origin_name,
        FileModel.is_deleted == False,
        FileModel.space_id == actual_space_id
    )
    if folder_id:
        existing_query = existing_query.where(FileModel.folder_id == folder_id)
    else:
        existing_query = existing_query.where(FileModel.folder_id == None)

    existing_result = await db.execute(existing_query)
    existing_file = existing_result.scalar_one_or_none()

    if existing_file:
        if overwrite:
            import shutil
            version_dir = os.path.join(os.path.dirname(existing_file.storage_path), "versions")
            os.makedirs(version_dir, exist_ok=True)
            old_version_path = os.path.join(version_dir, f"{existing_file.id}_v{existing_file.version_no}")

            if os.path.exists(existing_file.storage_path):
                shutil.copy2(existing_file.storage_path, old_version_path)

                old_version = FileVersion(
                    file_id=existing_file.id,
                    version_no=existing_file.version_no,
                    storage_path=old_version_path,
                    size=existing_file.size,
                    hash_sha256=existing_file.hash_sha256,
                    created_by=current_user.id
                )
                db.add(old_version)

            storage_path = existing_file.storage_path
            file_size, file_hash = await stream_file_to_disk(file, storage_path)

            existing_file.size = file_size
            existing_file.updated_at = get_beijing_time()
            existing_file.version_no += 1
            existing_file.hash_sha256 = file_hash

            await db.commit()
            await db.refresh(existing_file)

            await log_audit(
                db, current_user, "file_upload_overwrite", "file", existing_file.id, existing_file.origin_name, request,
                detail={"size": file_size, "ext": ext, "version": existing_file.version_no}
            )

            return FileResponse.model_validate(existing_file)
        else:
            base_name = origin_name.rsplit(".", 1)[0] if "." in origin_name else origin_name
            counter = 1
            while True:
                new_name = f"{base_name} ({counter}).{ext}" if ext else f"{base_name} ({counter})"
                check_query = select(FileModel).where(
                    FileModel.origin_name == new_name,
                    FileModel.is_deleted == False,
                    FileModel.space_id == actual_space_id
                )
                if folder_id:
                    check_query = check_query.where(FileModel.folder_id == folder_id)
                else:
                    check_query = check_query.where(FileModel.folder_id == None)
                if not (await db.execute(check_query)).scalar_one_or_none():
                    origin_name = new_name
                    break
                counter += 1

    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    storage_path = os.path.join(settings.STORAGE_PATH, folder_path, stored_name) if folder_path else os.path.join(settings.STORAGE_PATH, stored_name)

    file_size, file_hash = await stream_file_to_disk(file, storage_path)

    file_record = FileModel(
        space_id=actual_space_id,
        folder_id=folder_id,
        origin_name=origin_name,
        stored_name=stored_name,
        storage_path=storage_path,
        ext=ext,
        mime_type=file.content_type,
        size=file_size,
        hash_sha256=file_hash,
        owner_id=current_user.id,
        remark=remark,
        version_no=1,
        category_id=category_id,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    version = FileVersion(
        file_id=file_record.id,
        version_no=1,
        storage_path=storage_path,
        size=file_size,
        hash_sha256=file_hash,
        created_by=current_user.id
    )
    db.add(version)
    await db.commit()

    await log_audit(
        db, current_user, "file_upload", "file", file_record.id, file_record.origin_name, request,
        detail={"size": file_size, "ext": ext, "space_id": actual_space_id}
    )

    # 发送新文件通知（如果是群组空间）
    if actual_space_id:
        result = await db.execute(select(Space).where(Space.id == actual_space_id))
        space = result.scalar_one_or_none()
        if space and space.space_type == "group" and space.group_id:
            # 获取群组成员
            result = await db.execute(
                select(GroupMember).where(
                    GroupMember.group_id == space.group_id,
                    GroupMember.join_status == "active"
                )
            )
            members = result.scalars().all()
            member_ids = [m.user_id for m in members if m.user_id != current_user.id]

            if member_ids:
                await notify_new_file(
                    space.group_id,
                    {
                        "id": file_record.id,
                        "name": file_record.origin_name,
                        "size": len(content),
                        "uploader": current_user.real_name or current_user.username
                    },
                    member_ids
                )

    # 重新加载file_record以包含category关系
    result = await db.execute(
        select(FileModel).options(
            selectinload(FileModel.owner),
            selectinload(FileModel.category)
        ).where(FileModel.id == file_record.id)
    )
    file_record = result.scalar_one()

    return FileResponse.model_validate(file_record)


@router.post("/upload-folder")
async def upload_folder(
    request: Request,
    files: List[UploadFile] = FastAPIFile(...),
    paths: str = Form(...),
    space_id: Optional[int] = Query(None),
    current_user: User = Depends(require_permission("file:upload")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件夹（批量上传，保持目录结构）"""
    import json

    path_list = json.loads(paths)

    if len(files) != len(path_list):
        raise HTTPException(status_code=400, detail="文件数量与路径数量不匹配")

    actual_space_id = space_id
    if not actual_space_id:
        result = await db.execute(
            select(Space).where(Space.space_type == "personal", Space.owner_id == current_user.id)
        )
        personal_space = result.scalar_one_or_none()
        if personal_space:
            actual_space_id = personal_space.id

    if not actual_space_id:
        raise HTTPException(status_code=400, detail="未指定空间且无个人空间")

    root_folder_name = path_list[0].split("/")[0] if path_list else "新建文件夹"

    existing_query = select(Folder).where(
        Folder.name == root_folder_name,
        Folder.is_deleted == False,
        Folder.parent_id == None,
        Folder.space_id == actual_space_id
    )
    existing_result = await db.execute(existing_query)
    root_folder = existing_result.scalar_one_or_none()

    if not root_folder:
        root_folder = Folder(
            space_id=actual_space_id,
            name=root_folder_name,
            parent_id=None,
            owner_id=current_user.id,
        )
        db.add(root_folder)
        await db.flush()
        root_folder.path = f"/{root_folder.id}"
        await db.flush()

    folder_cache = {root_folder_name: root_folder}

    uploaded_count = 0
    errors = []

    for i, (file, rel_path) in enumerate(zip(files, path_list)):
        try:
            parts = rel_path.split("/")
            current_parent_id = root_folder.id

            for j in range(1, len(parts) - 1):
                folder_name = parts[j]
                cache_key = "/".join(parts[:j + 1])

                if cache_key in folder_cache:
                    current_parent_id = folder_cache[cache_key].id
                    continue

                result = await db.execute(
                    select(Folder).where(
                        Folder.name == folder_name,
                        Folder.parent_id == current_parent_id,
                        Folder.is_deleted == False,
                        Folder.space_id == actual_space_id
                    )
                )
                sub_folder = result.scalar_one_or_none()

                if not sub_folder:
                    sub_folder = Folder(
                        space_id=actual_space_id,
                        name=folder_name,
                        parent_id=current_parent_id,
                        owner_id=current_user.id,
                    )
                    db.add(sub_folder)
                    await db.flush()
                    parent_folder = folder_cache.get("/".join(parts[:j]))
                    sub_folder.path = f"{parent_folder.path}/{sub_folder.id}" if parent_folder else f"/{sub_folder.id}"
                    await db.flush()

                folder_cache[cache_key] = sub_folder
                current_parent_id = sub_folder.id

            content = await file.read()
            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

            stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
            parent_folder_obj = folder_cache.get("/".join(parts[:-1]), root_folder)
            folder_path = parent_folder_obj.path.strip("/") if parent_folder_obj else ""
            storage_path = os.path.join(settings.STORAGE_PATH, folder_path, stored_name) if folder_path else os.path.join(settings.STORAGE_PATH, stored_name)

            storage_dir = os.path.dirname(storage_path)
            if storage_dir:
                os.makedirs(storage_dir, exist_ok=True)
            else:
                os.makedirs(settings.STORAGE_PATH, exist_ok=True)

            async with aiofiles.open(storage_path, "wb") as f:
                await f.write(content)

            file_hash = get_file_hash(storage_path)

            file_record = FileModel(
                space_id=actual_space_id,
                folder_id=current_parent_id,
                origin_name=file.filename,
                stored_name=stored_name,
                storage_path=storage_path,
                ext=ext,
                mime_type=file.content_type,
                size=len(content),
                hash_sha256=file_hash,
                owner_id=current_user.id,
                version_no=1,
            )
            db.add(file_record)
            uploaded_count += 1

        except Exception as e:
            errors.append({"file": rel_path, "error": str(e)})

    await db.commit()

    await log_audit(
        db, current_user, "folder_upload", "folder", root_folder.id, root_folder_name, request,
        detail={"file_count": uploaded_count, "root_folder": root_folder_name}
    )

    return {
        "message": f"成功上传 {uploaded_count} 个文件到文件夹 {root_folder_name}",
        "folder_id": root_folder.id,
        "folder_name": root_folder_name,
        "uploaded_count": uploaded_count,
        "errors": errors
    }


@router.put("/{file_id}/rename", response_model=FileResponse)
async def rename_file(
    file_id: int,
    data: dict = Body(...),
    request: Request = None,
    current_user: User = Depends(require_permission("file:rename")),
    db: AsyncSession = Depends(get_db),
):
    """重命名文件"""
    new_name = data.get("name")
    if not new_name:
        raise HTTPException(status_code=400, detail="请提供新文件名")

    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 检查重名
    query = select(FileModel).where(
        FileModel.origin_name == new_name,
        FileModel.is_deleted == False,
        FileModel.id != file_id
    )
    if file_record.folder_id:
        query = query.where(FileModel.folder_id == file_record.folder_id)
    else:
        query = query.where(FileModel.folder_id == None)

    if (await db.execute(query)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="同名文件已存在")

    old_name = file_record.origin_name
    file_record.origin_name = new_name
    await db.commit()

    await log_audit(
        db, current_user, "file_rename", "file", file_record.id, file_record.origin_name, request,
        detail={"old_name": old_name, "new_name": new_name}
    )

    return FileResponse.model_validate(file_record)


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """下载文件"""
    import traceback
    from app.core.security import decode_access_token

    try:
        current_user = None

        # 优先从查询参数获取token
        if token:
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    result = await db.execute(select(User).where(User.id == int(user_id)))
                    current_user = result.scalar_one_or_none()

        # 如果查询参数没有token，尝试从Authorization header获取
        if not current_user:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                payload = decode_access_token(token)
                if payload:
                    user_id = payload.get("sub")
                    if user_id:
                        result = await db.execute(select(User).where(User.id == int(user_id)))
                        current_user = result.scalar_one_or_none()

        if not current_user:
            raise HTTPException(status_code=401, detail="需要认证")

        # 检查权限
        if not current_user.is_superuser:
            result = await db.execute(
                select(Permission)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == current_user.role_id)
                .where(Permission.code == "file:download")
            )
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="没有下载权限")

        result = await db.execute(
            select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
        )
        file_record = result.scalar_one_or_none()

        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 处理相对路径 - 转换为绝对路径
        storage_path = file_record.storage_path
        if not os.path.isabs(storage_path):
            # 先尝试使用 settings.STORAGE_PATH + 文件名
            storage_path = os.path.join(settings.STORAGE_PATH, os.path.basename(storage_path))
            if not os.path.exists(storage_path):
                # 再尝试相对路径转绝对路径
                storage_path = os.path.abspath(file_record.storage_path)

        if not os.path.exists(storage_path):
            raise HTTPException(status_code=404, detail="文件已被删除")

        await log_audit(
            db, current_user, "file_download", "file", file_record.id, file_record.origin_name, request
        )

        return FastAPIFileResponse(
            path=storage_path,
            filename=file_record.origin_name,
            media_type=file_record.mime_type or "application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Download error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.post("/batch-download")
async def batch_download(
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(require_permission("file:download")),
    db: AsyncSession = Depends(get_db),
):
    """批量下载文件（打包成zip）"""
    file_ids = data.get("file_ids", [])
    if not file_ids:
        raise HTTPException(status_code=400, detail="请选择要下载的文件")

    result = await db.execute(
        select(FileModel).where(FileModel.id.in_(file_ids), FileModel.is_deleted == False)
    )
    files = result.scalars().all()

    if not files:
        raise HTTPException(status_code=404, detail="没有找到可下载的文件")

    # 创建临时zip文件
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_record in files:
            if os.path.exists(file_record.storage_path):
                zipf.write(file_record.storage_path, file_record.origin_name)

    await log_audit(
        db, current_user, "file_batch_download", "file", 0, f"{len(files)}个文件", request,
        detail={"file_ids": file_ids}
    )

    def iterfile():
        with open(tmp_path, 'rb') as f:
            yield from f
        os.unlink(tmp_path)

    return StreamingResponse(
        iterfile(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=download_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"}
    )


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """预览文件"""
    from app.core.security import decode_access_token

    current_user = None

    # 优先从查询参数获取token
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == int(user_id)))
                current_user = result.scalar_one_or_none()

    # 如果查询参数没有token，尝试从Authorization header获取
    if not current_user:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    result = await db.execute(select(User).where(User.id == int(user_id)))
                    current_user = result.scalar_one_or_none()

    if not current_user:
        raise HTTPException(status_code=401, detail="需要认证")

    # 检查权限
    if not current_user.is_superuser:
        result = await db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == current_user.role_id)
            .where(Permission.code == "file:view")
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="没有查看权限")

    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 处理相对路径 - 转换为绝对路径
    storage_path = file_record.storage_path
    if not os.path.isabs(storage_path):
        storage_path = os.path.join(settings.STORAGE_PATH, os.path.basename(storage_path))
        if not os.path.exists(storage_path):
            storage_path = os.path.abspath(file_record.storage_path)

    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="文件已被删除")

    mime_type = file_record.mime_type or 'application/octet-stream'
    
    # 对于文本文件，自动检测编码并转换为 UTF-8
    if mime_type.startswith('text/'):
        async with aiofiles.open(storage_path, 'rb') as f:
            raw_data = await f.read()
        
        # 检测编码
        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'utf-8')
        print(f"[预览] 检测到编码: {encoding}, 文件: {file_record.origin_name}")
        
        # 对文件名进行 URL 编码
        encoded_filename = quote(file_record.origin_name)
        
        # 如果检测到 GBK/GB2312，转换为 UTF-8
        if encoding and encoding.lower() in ['gb2312', 'gbk', 'gb18030']:
            try:
                text_content = raw_data.decode('gbk')
                utf8_content = text_content.encode('utf-8')
                print(f"[预览] GBK转UTF-8成功, 内容前50字符: {text_content[:50]}")
                return Response(
                    content=utf8_content,
                    media_type='text/plain; charset=utf-8',
                    headers={
                        'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}",
                        'Cache-Control': 'no-cache'
                    }
                )
            except Exception as e:
                print(f"[预览] GBK解码失败: {e}")
        
        # 其他编码，尝试直接返回
        try:
            text_content = raw_data.decode(encoding or 'utf-8')
            utf8_content = text_content.encode('utf-8')
            print(f"[预览] 使用{encoding}解码成功")
            return Response(
                content=utf8_content,
                media_type='text/plain; charset=utf-8',
                headers={
                    'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}",
                    'Cache-Control': 'no-cache'
                }
            )
        except Exception as e:
            print(f"[预览] 解码失败: {e}")

    return FastAPIFileResponse(
        path=storage_path,
        media_type=mime_type,
        filename=file_record.origin_name,
        content_disposition_type="inline",
    )


@router.delete("/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(require_permission("file:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除文件 (移入回收站)"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_record.is_deleted = True
    file_record.status = 2
    await db.commit()

    await log_audit(
        db, current_user, "file_delete", "file", file_record.id, file_record.origin_name, request
    )

    return MessageResponse(message="文件已移入回收站")


@router.post("/batch-delete", response_model=MessageResponse)
async def batch_delete_files(
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(require_permission("file:delete")),
    db: AsyncSession = Depends(get_db),
):
    """批量删除文件"""
    file_ids = data.get("file_ids", [])
    if not file_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的文件")

    result = await db.execute(
        select(FileModel).where(FileModel.id.in_(file_ids), FileModel.is_deleted == False)
    )
    files = result.scalars().all()

    for file_record in files:
        file_record.is_deleted = True
        file_record.status = 2

    await db.commit()

    await log_audit(
        db, current_user, "file_batch_delete", "file", 0, f"{len(files)}个文件", request,
        detail={"file_ids": [f.id for f in files]}
    )

    return MessageResponse(message=f"已删除 {len(files)} 个文件")


@router.post("/{file_id}/move", response_model=FileResponse)
async def move_file(
    file_id: int,
    data: FileMove,
    request: Request,
    current_user: User = Depends(require_permission("file:move")),
    db: AsyncSession = Depends(get_db),
):
    """移动文件"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 目标文件夹
    if data.target_folder_id:
        result = await db.execute(
            select(Folder).where(Folder.id == data.target_folder_id, Folder.is_deleted == False)
        )
        target_folder = result.scalar_one_or_none()
        if not target_folder:
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
        folder_path = target_folder.path.strip("/")
    else:
        target_folder = None
        folder_path = ""

    # 移动物理文件
    old_path = file_record.storage_path
    new_path = os.path.join(settings.STORAGE_PATH, folder_path, file_record.stored_name) if folder_path else os.path.join(settings.STORAGE_PATH, file_record.stored_name)

    if old_path != new_path:
        os.makedirs(os.path.dirname(new_path) if os.path.dirname(new_path) else settings.STORAGE_PATH, exist_ok=True)
        if os.path.exists(old_path):
            os.rename(old_path, new_path)

    file_record.folder_id = data.target_folder_id
    file_record.storage_path = new_path
    await db.commit()

    await log_audit(
        db, current_user, "file_move", "file", file_record.id, file_record.origin_name, request,
        detail={"target_folder": target_folder.name if target_folder else "根目录"}
    )

    return FileResponse.model_validate(file_record)


@router.post("/{file_id}/copy", response_model=FileResponse)
async def copy_file(
    file_id: int,
    data: FileCopy,
    request: Request,
    current_user: User = Depends(require_permission("file:copy")),
    db: AsyncSession = Depends(get_db),
):
    """复制文件"""
    import shutil

    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    source_file = result.scalar_one_or_none()

    if not source_file:
        raise HTTPException(status_code=404, detail="源文件不存在")

    # 目标文件夹
    if data.target_folder_id:
        result = await db.execute(
            select(Folder).where(Folder.id == data.target_folder_id, Folder.is_deleted == False)
        )
        target_folder = result.scalar_one_or_none()
        if not target_folder:
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
        folder_path = target_folder.path.strip("/")
    else:
        target_folder = None
        folder_path = ""

    new_name = data.new_name or f"副本_{source_file.origin_name}"
    new_stored_name = f"{uuid.uuid4().hex}.{source_file.ext}" if source_file.ext else uuid.uuid4().hex
    new_path = os.path.join(settings.STORAGE_PATH, folder_path, new_stored_name) if folder_path else os.path.join(settings.STORAGE_PATH, new_stored_name)

    os.makedirs(os.path.dirname(new_path) if os.path.dirname(new_path) else settings.STORAGE_PATH, exist_ok=True)
    shutil.copy2(source_file.storage_path, new_path)

    new_file = FileModel(
        folder_id=data.target_folder_id,
        origin_name=new_name,
        stored_name=new_stored_name,
        storage_path=new_path,
        ext=source_file.ext,
        mime_type=source_file.mime_type,
        size=source_file.size,
        hash_sha256=source_file.hash_sha256,
        owner_id=current_user.id,
    )
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)

    await log_audit(
        db, current_user, "file_copy", "file", new_file.id, new_file.origin_name, request,
        detail={"source_file": source_file.origin_name}
    )

    return FileResponse.model_validate(new_file)


# ==================== 回收站 ====================

@router.get("/trash/list", response_model=FileListResponse)
async def list_trash(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取回收站文件列表"""
    query = select(FileModel).options(selectinload(FileModel.owner)).where(FileModel.status == 2)

    # 普通用户只能看自己删除的
    if not current_user.is_superuser:
        query = query.where(FileModel.owner_id == current_user.id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(FileModel.updated_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trash/{file_id}/restore", response_model=MessageResponse)
async def restore_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(require_permission("file:delete")),
    db: AsyncSession = Depends(get_db),
):
    """恢复文件"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.status == 2)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不在回收站中")

    file_record.is_deleted = False
    file_record.status = 1
    await db.commit()

    await log_audit(db, current_user, "file_restore", "file", file_record.id, file_record.origin_name, request)

    return MessageResponse(message="文件已恢复")


@router.delete("/trash/{file_id}", response_model=MessageResponse)
async def permanent_delete_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """彻底删除文件（管理员）"""
    from app.api.deps import get_superuser

    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 删除物理文件
    if os.path.exists(file_record.storage_path):
        os.remove(file_record.storage_path)

    await db.delete(file_record)
    await db.commit()

    await log_audit(db, current_user, "file_permanent_delete", "file", file_record.id, file_record.origin_name, request)

    return MessageResponse(message="文件已彻底删除")


@router.delete("/trash", response_model=MessageResponse)
async def empty_trash(
    request: Request,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_db),
):
    """清空回收站（管理员）"""
    result = await db.execute(
        select(FileModel).where(FileModel.status == 2)
    )
    files = result.scalars().all()

    for file_record in files:
        if os.path.exists(file_record.storage_path):
            os.remove(file_record.storage_path)
        await db.delete(file_record)

    await db.commit()

    await log_audit(db, current_user, "trash_empty", "system", 0, "回收站", request, detail={"count": len(files)})

    return MessageResponse(message=f"已清空回收站，删除 {len(files)} 个文件")


# ==================== 搜索 ====================

@router.get("/search", response_model=FileListResponse)
async def search_files(
    keyword: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ext: Optional[str] = None,
    owner_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索文件"""
    query = select(FileModel).options(selectinload(FileModel.owner)).where(FileModel.is_deleted == False)

    query = query.where(FileModel.origin_name.ilike(f"%{keyword}%"))

    if ext:
        query = query.where(FileModel.ext == ext.lower())
    if owner_id:
        query = query.where(FileModel.owner_id == owner_id)
    if date_from:
        query = query.where(FileModel.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(FileModel.created_at <= datetime.fromisoformat(date_to))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(FileModel.created_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/public/search", response_model=FileListResponse)
async def search_public_files(
    keyword: str = Query(..., min_length=1),
    category_id: Optional[int] = None,
    ext: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索公共空间文件"""
    # 获取公共空间
    result = await db.execute(
        select(Space).where(Space.space_type == "public", Space.status == True)
    )
    public_space = result.scalar_one_or_none()

    if not public_space:
        return FileListResponse(items=[], total=0, page=page, page_size=page_size)

    # 构建查询
    query = select(FileModel).options(
        selectinload(FileModel.owner),
        selectinload(FileModel.category)
    ).where(
        FileModel.is_deleted == False,
        FileModel.space_id == public_space.id
    )

    # 关键词搜索
    query = query.where(FileModel.origin_name.ilike(f"%{keyword}%"))

    # 分类筛选
    if category_id:
        query = query.where(FileModel.category_id == category_id)

    # 扩展名筛选
    if ext:
        query = query.where(FileModel.ext == ext.lower())

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页和排序
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(FileModel.created_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/public", response_model=FileListResponse)
async def list_public_files(
    category_id: Optional[int] = None,
    ext: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取公共空间文件列表"""
    # 获取公共空间
    result = await db.execute(
        select(Space).where(Space.space_type == "public", Space.status == True)
    )
    public_space = result.scalar_one_or_none()

    if not public_space:
        return FileListResponse(items=[], total=0, page=page, page_size=page_size)

    # 构建查询
    query = select(FileModel).options(
        selectinload(FileModel.owner),
        selectinload(FileModel.category)
    ).where(
        FileModel.is_deleted == False,
        FileModel.space_id == public_space.id
    )

    # 分类筛选
    if category_id:
        query = query.where(FileModel.category_id == category_id)

    # 扩展名筛选
    if ext:
        query = query.where(FileModel.ext == ext.lower())

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页和排序
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(FileModel.created_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== 用户统计 ====================

@router.get("/my/stats")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的存储统计"""
    # 文件数量
    file_count = (await db.execute(
        select(func.count()).select_from(FileModel)
        .where(FileModel.owner_id == current_user.id)
        .where(FileModel.is_deleted == False)
    )).scalar() or 0

    # 文件夹数量
    folder_count = (await db.execute(
        select(func.count()).select_from(Folder)
        .where(Folder.owner_id == current_user.id)
        .where(Folder.is_deleted == False)
    )).scalar() or 0

    # 总大小
    total_size = (await db.execute(
        select(func.coalesce(func.sum(FileModel.size), 0))
        .where(FileModel.owner_id == current_user.id)
        .where(FileModel.is_deleted == False)
    )).scalar() or 0

    # 按类型统计
    type_result = await db.execute(
        select(
            FileModel.ext,
            func.count().label("count"),
            func.sum(FileModel.size).label("size")
        )
        .where(FileModel.owner_id == current_user.id)
        .where(FileModel.is_deleted == False)
        .group_by(FileModel.ext)
    )
    type_rows = type_result.all()

    total_file_count = sum(r.count for r in type_rows) or 1
    by_type = [
        {
            "ext": r.ext or "其他",
            "count": r.count,
            "size": r.size or 0,
            "percentage": round(r.count / total_file_count * 100, 1)
        }
        for r in type_rows[:10]
    ]

    return {
        "file_count": file_count,
        "folder_count": folder_count,
        "total_size": total_size,
        "by_type": by_type
    }
