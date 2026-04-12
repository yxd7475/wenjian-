"""
文件管理 API 路由
"""
import os
import uuid
import hashlib
import aiofiles
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, File as FileModel, Folder, AuditLog, UploadTask
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
from app.api.deps import get_current_user, require_permission

router = APIRouter(prefix="/files", tags=["文件管理"])


def get_file_hash(file_path: str) -> str:
    """计算文件SHA256哈希"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文件夹树"""
    result = await db.execute(
        select(Folder)
        .where(Folder.is_deleted == False)
        .order_by(Folder.name)
    )
    folders = result.scalars().all()

    # 构建树形结构
    folder_map = {f.id: FolderTree.model_validate(f) for f in folders}
    root_folders = []

    for folder in folders:
        folder_tree = folder_map[folder.id]
        if folder.parent_id is None:
            root_folders.append(folder_tree)
        elif folder.parent_id in folder_map:
            folder_map[folder.parent_id].children.append(folder_tree)

    return root_folders


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    data: FolderCreate,
    request: Request,
    current_user: User = Depends(require_permission("folder:create")),
    db: AsyncSession = Depends(get_db),
):
    """创建文件夹"""
    # 检查父文件夹是否存在
    if data.parent_id:
        result = await db.execute(
            select(Folder).where(Folder.id == data.parent_id, Folder.is_deleted == False)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父文件夹不存在",
            )

    # 创建文件夹
    folder = Folder(
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
    """删除文件夹 (软删除)"""
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.is_deleted == False)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在",
        )

    # 检查是否有子文件夹
    result = await db.execute(
        select(Folder).where(Folder.parent_id == folder_id, Folder.is_deleted == False)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件夹不为空，请先删除子文件夹",
        )

    folder.is_deleted = True
    await db.commit()

    await log_audit(db, current_user, "folder_delete", "folder", folder.id, folder.name, request)

    return MessageResponse(message="文件夹已删除")


# ==================== 文件管理 ====================

@router.get("", response_model=FileListResponse)
async def list_files(
    folder_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    ext: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文件列表"""
    query = select(FileModel).where(FileModel.is_deleted == False)

    if folder_id:
        query = query.where(FileModel.folder_id == folder_id)
    if keyword:
        query = query.where(FileModel.origin_name.ilike(f"%{keyword}%"))
    if ext:
        query = query.where(FileModel.ext == ext.lower())

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
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    remark: Optional[str] = Form(None),
    current_user: User = Depends(require_permission("file:upload")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件 (简单上传)"""
    # 检查文件扩展名
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {ext}",
        )

    # 检查文件大小
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB)",
        )

    # 确定存储路径
    folder_path = ""
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
        folder_path = folder.path.strip("/")

    # 生成存储文件名
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    storage_path = os.path.join(settings.STORAGE_PATH, folder_path, stored_name)

    # 确保目录存在
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    # 写入文件
    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)

    # 计算哈希
    file_hash = get_file_hash(storage_path)

    # 保存到数据库
    file_record = FileModel(
        folder_id=folder_id,
        origin_name=file.filename,
        stored_name=stored_name,
        storage_path=storage_path,
        ext=ext,
        mime_type=file.content_type,
        size=len(content),
        hash_sha256=file_hash,
        owner_id=current_user.id,
        remark=remark,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    await log_audit(
        db, current_user, "file_upload", "file", file_record.id, file_record.origin_name, request,
        detail={"size": len(content), "ext": ext}
    )

    return FileResponse.model_validate(file_record)


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(require_permission("file:download")),
    db: AsyncSession = Depends(get_db),
):
    """下载文件"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    if not os.path.exists(file_record.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已被删除",
        )

    await log_audit(
        db, current_user, "file_download", "file", file_record.id, file_record.origin_name, request
    )

    return FileResponse(
        path=file_record.storage_path,
        filename=file_record.origin_name,
        media_type=file_record.mime_type or "application/octet-stream",
    )


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    current_user: User = Depends(require_permission("file:view")),
    db: AsyncSession = Depends(get_db),
):
    """预览文件"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    if not os.path.exists(file_record.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已被删除",
        )

    # 根据文件类型返回预览
    preview_types = [
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
        "application/pdf",
        "text/plain", "text/markdown", "text/html",
    ]

    if file_record.mime_type not in preview_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该文件类型不支持预览",
        )

    return FileResponse(
        path=file_record.storage_path,
        media_type=file_record.mime_type,
    )


@router.delete("/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(require_permission("file:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除文件 (软删除)"""
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    file_record.is_deleted = True
    file_record.status = 2  # 回收站
    await db.commit()

    await log_audit(
        db, current_user, "file_delete", "file", file_record.id, file_record.origin_name, request
    )

    return MessageResponse(message="文件已移入回收站")


@router.post("/{file_id}/move", response_model=FileResponse)
async def move_file(
    file_id: int,
    data: FileMove,
    request: Request,
    current_user: User = Depends(require_permission("file:move")),
    db: AsyncSession = Depends(get_db),
):
    """移动文件"""
    # 获取文件
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    # 获取目标文件夹
    result = await db.execute(
        select(Folder).where(Folder.id == data.target_folder_id, Folder.is_deleted == False)
    )
    target_folder = result.scalar_one_or_none()

    if not target_folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标文件夹不存在",
        )

    # 移动物理文件
    old_path = file_record.storage_path
    new_path = os.path.join(settings.STORAGE_PATH, target_folder.path.strip("/"), file_record.stored_name)
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    os.rename(old_path, new_path)

    # 更新数据库
    file_record.folder_id = target_folder.id
    file_record.storage_path = new_path
    await db.commit()

    await log_audit(
        db, current_user, "file_move", "file", file_record.id, file_record.origin_name, request,
        detail={"target_folder": target_folder.name}
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
    # 获取源文件
    result = await db.execute(
        select(FileModel).where(FileModel.id == file_id, FileModel.is_deleted == False)
    )
    source_file = result.scalar_one_or_none()

    if not source_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源文件不存在",
        )

    # 获取目标文件夹
    result = await db.execute(
        select(Folder).where(Folder.id == data.target_folder_id, Folder.is_deleted == False)
    )
    target_folder = result.scalar_one_or_none()

    if not target_folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标文件夹不存在",
        )

    # 复制物理文件
    new_name = data.new_name or f"副本_{source_file.origin_name}"
    new_stored_name = f"{uuid.uuid4().hex}.{source_file.ext}" if source_file.ext else uuid.uuid4().hex
    new_path = os.path.join(settings.STORAGE_PATH, target_folder.path.strip("/"), new_stored_name)

    os.makedirs(os.path.dirname(new_path), exist_ok=True)

    # 复制文件内容
    import shutil
    shutil.copy2(source_file.storage_path, new_path)

    # 创建新文件记录
    new_file = FileModel(
        folder_id=target_folder.id,
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
