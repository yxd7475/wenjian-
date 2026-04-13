"""
分片上传 API
"""
import os
import uuid
import hashlib
import aiofiles
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import User, UploadTask, File, Folder, FileVersion
from app.api.deps import get_current_user
from app.core.config import settings
from app.api.files import log_audit

router = APIRouter(prefix="/upload", tags=["分片上传"])


class UploadInitRequest(BaseModel):
    file_name: str
    file_size: int
    chunk_size: int = 5 * 1024 * 1024  # 默认5MB
    folder_id: Optional[int] = None


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    chunk_total: int


class ChunkUploadResponse(BaseModel):
    upload_id: str
    chunk_index: int
    chunk_uploaded: int
    chunk_total: int
    status: int


class UploadStatusResponse(BaseModel):
    upload_id: str
    file_name: str
    file_size: int
    chunk_total: int
    chunk_uploaded: int
    status: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    data: UploadInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """初始化分片上传"""
    # 计算分片数量
    chunk_total = (data.file_size + data.chunk_size - 1) // data.chunk_size

    # 生成上传ID
    upload_id = str(uuid.uuid4())

    # 创建上传任务
    task = UploadTask(
        user_id=current_user.id,
        file_name=data.file_name,
        file_size=data.file_size,
        chunk_total=chunk_total,
        chunk_uploaded=0,
        chunk_size=data.chunk_size,
        upload_id=upload_id,
        status=0,  # 等待上传
    )
    db.add(task)
    await db.commit()

    # 创建临时目录
    temp_dir = os.path.join(settings.UPLOAD_TEMP_PATH, upload_id)
    os.makedirs(temp_dir, exist_ok=True)

    return UploadInitResponse(
        upload_id=upload_id,
        chunk_size=data.chunk_size,
        chunk_total=chunk_total
    )


@router.post("/chunk", response_model=ChunkUploadResponse)
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传分片"""
    # 获取上传任务
    result = await db.execute(
        select(UploadTask).where(UploadTask.upload_id == upload_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限")

    if task.status == 2:
        raise HTTPException(status_code=400, detail="上传已完成")

    # 保存分片
    temp_dir = os.path.join(settings.UPLOAD_TEMP_PATH, upload_id)
    chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index}")

    async with aiofiles.open(chunk_path, 'wb') as f:
        content = await chunk.read()
        await f.write(content)

    # 更新任务状态
    if task.status == 0:
        task.status = 1  # 上传中

    # 检查所有分片
    uploaded_chunks = len([f for f in os.listdir(temp_dir) if f.startswith("chunk_")])
    task.chunk_uploaded = uploaded_chunks
    await db.commit()

    return ChunkUploadResponse(
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_uploaded=uploaded_chunks,
        chunk_total=task.chunk_total,
        status=task.status
    )


@router.post("/complete")
async def complete_upload(
    upload_id: str,
    folder_id: Optional[int] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """完成分片上传"""
    result = await db.execute(
        select(UploadTask).where(UploadTask.upload_id == upload_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限")

    temp_dir = os.path.join(settings.UPLOAD_TEMP_PATH, upload_id)

    # 检查分片是否完整
    uploaded_chunks = sorted([
        int(f.split("_")[1]) for f in os.listdir(temp_dir) if f.startswith("chunk_")
    ])

    if len(uploaded_chunks) != task.chunk_total:
        raise HTTPException(
            status_code=400,
            detail=f"分片不完整，已上传 {len(uploaded_chunks)}/{task.chunk_total}"
        )

    # 合并文件
    ext = task.file_name.rsplit('.', 1)[-1].lower() if '.' in task.file_name else ''
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    storage_path = os.path.join(settings.STORAGE_PATH, stored_name[:2], stored_name)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    # 计算哈希并合并
    sha256_hash = hashlib.sha256()
    async with aiofiles.open(storage_path, 'wb') as outfile:
        for i in range(task.chunk_total):
            chunk_path = os.path.join(temp_dir, f"chunk_{i}")
            async with aiofiles.open(chunk_path, 'rb') as infile:
                content = await infile.read()
                sha256_hash.update(content)
                await outfile.write(content)

    file_hash = sha256_hash.hexdigest()

    # 检查是否已存在相同文件（秒传）
    result = await db.execute(
        select(File)
        .where(File.hash_sha256 == file_hash)
        .where(File.is_deleted == False)
    )
    existing_file = result.scalar_one_or_none()

    if existing_file:
        # 秒传：创建新文件记录指向相同存储
        file = File(
            folder_id=folder_id,
            origin_name=task.file_name,
            stored_name=existing_file.stored_name,
            storage_path=existing_file.storage_path,
            ext=ext,
            mime_type=existing_file.mime_type,
            size=task.file_size,
            hash_sha256=file_hash,
            owner_id=current_user.id,
            version_no=1,
            status=1,
        )
    else:
        # 正常上传
        mime_types = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif',
            'pdf': 'application/pdf', 'txt': 'text/plain', 'md': 'text/markdown',
            'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'mp3': 'audio/mpeg', 'mp4': 'video/mp4', 'zip': 'application/zip',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

        file = File(
            folder_id=folder_id,
            origin_name=task.file_name,
            stored_name=stored_name,
            storage_path=storage_path,
            ext=ext,
            mime_type=mime_type,
            size=task.file_size,
            hash_sha256=file_hash,
            owner_id=current_user.id,
            version_no=1,
            status=1,
        )

    db.add(file)

    # 创建初始版本记录
    version = FileVersion(
        file_id=file.id,
        version_no=1,
        storage_path=storage_path,
        size=task.file_size,
        hash_sha256=file_hash,
        created_by=current_user.id
    )
    db.add(version)

    # 更新任务状态
    task.status = 2
    task.storage_path = storage_path
    await db.commit()

    # 清理临时文件
    shutil.rmtree(temp_dir, ignore_errors=True)

    # 记录审计日志
    await log_audit(
        db, current_user, "file_upload", "file", file.id,
        file.origin_name, request, detail={"size": file.size, "upload_id": upload_id}
    )

    return {
        "message": "上传完成",
        "file_id": file.id,
        "file_name": file.origin_name,
        "size": file.size,
        "is_instant": existing_file is not None
    }


@router.get("/status/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取上传状态"""
    result = await db.execute(
        select(UploadTask).where(UploadTask.upload_id == upload_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限")

    return UploadStatusResponse(
        upload_id=task.upload_id,
        file_name=task.file_name,
        file_size=task.file_size,
        chunk_total=task.chunk_total,
        chunk_uploaded=task.chunk_uploaded,
        status=task.status,
        created_at=task.created_at
    )


@router.get("/tasks", response_model=List[UploadStatusResponse])
async def list_upload_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我的上传任务列表"""
    result = await db.execute(
        select(UploadTask)
        .where(UploadTask.user_id == current_user.id)
        .order_by(UploadTask.created_at.desc())
        .limit(20)
    )
    tasks = result.scalars().all()

    return [
        UploadStatusResponse(
            upload_id=t.upload_id,
            file_name=t.file_name,
            file_size=t.file_size,
            chunk_total=t.chunk_total,
            chunk_uploaded=t.chunk_uploaded,
            status=t.status,
            created_at=t.created_at
        )
        for t in tasks
    ]


@router.delete("/{upload_id}")
async def cancel_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消/删除上传任务"""
    result = await db.execute(
        select(UploadTask).where(UploadTask.upload_id == upload_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限")

    # 清理临时文件
    temp_dir = os.path.join(settings.UPLOAD_TEMP_PATH, upload_id)
    shutil.rmtree(temp_dir, ignore_errors=True)

    await db.delete(task)
    await db.commit()

    return {"message": "已取消"}
