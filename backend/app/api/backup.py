"""
备份恢复 API
"""
import os
import shutil
import zipfile
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.session import get_db, engine
from app.models.models import User, BackupRecord, File
from app.api.deps import get_superuser
from app.core.config import settings
from app.api.files import log_audit
from app.utils.scheduler import update_backup_schedule, get_backup_schedule

router = APIRouter(prefix="/backup", tags=["备份恢复"])


class BackupResponse(BaseModel):
    id: int
    backup_type: str
    file_path: str
    file_size: int
    status: int
    message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class BackupConfig(BaseModel):
    backup_type: str = "full"  # full/data/files
    include_files: bool = True


async def run_backup(backup_id: int, backup_type: str, include_files: bool, user_id: int):
    """后台执行备份任务"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # 获取备份记录
            result = await db.execute(
                select(BackupRecord).where(BackupRecord.id == backup_id)
            )
            backup = result.scalar_one()
            backup.status = 0  # 进行中
            await db.commit()

            # 创建备份目录
            backup_dir = os.path.join(settings.STORAGE_PATH, "..", "backups")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{backup_type}_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_filename)

            if backup_type == "data" or backup_type == "full":
                # 数据库备份
                db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
                if os.path.exists(db_path):
                    db_backup_path = backup_path + ".db"
                    shutil.copy2(db_path, db_backup_path)

            if (backup_type == "files" or backup_type == "full") and include_files:
                # 文件备份
                storage_path = settings.STORAGE_PATH
                if os.path.exists(storage_path):
                    files_backup_path = backup_path + "_files.zip"
                    with zipfile.ZipFile(files_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(storage_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, storage_path)
                                zipf.write(file_path, arcname)

            # 计算备份大小
            total_size = 0
            for f in os.listdir(backup_dir):
                if f.startswith(f"backup_{backup_type}_{timestamp[:15]}"):
                    total_size += os.path.getsize(os.path.join(backup_dir, f))

            backup.file_path = backup_path
            backup.file_size = total_size
            backup.status = 1  # 成功
            backup.message = "备份完成"
            await db.commit()

        except Exception as e:
            backup.status = 2  # 失败
            backup.message = str(e)
            await db.commit()


@router.post("", response_model=BackupResponse)
async def create_backup(
    data: BackupConfig,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """创建备份"""
    # 创建备份记录
    backup = BackupRecord(
        backup_type=data.backup_type,
        file_path="",
        file_size=0,
        status=0,
        created_by=current_user.id
    )
    db.add(backup)
    await db.commit()
    await db.refresh(backup)

    # 后台执行备份
    background_tasks.add_task(
        run_backup, backup.id, data.backup_type, data.include_files, current_user.id
    )

    await log_audit(
        db, current_user, "backup_create", "system", backup.id,
        f"{data.backup_type}备份", request
    )

    return BackupResponse(
        id=backup.id,
        backup_type=backup.backup_type,
        file_path=backup.file_path,
        file_size=backup.file_size,
        status=backup.status,
        message=backup.message,
        created_at=backup.created_at
    )


@router.get("", response_model=List[BackupResponse])
async def list_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """获取备份列表"""
    result = await db.execute(
        select(BackupRecord)
        .order_by(desc(BackupRecord.created_at))
        .limit(50)
    )
    backups = result.scalars().all()

    return [
        BackupResponse(
            id=b.id,
            backup_type=b.backup_type,
            file_path=b.file_path,
            file_size=b.file_size,
            status=b.status,
            message=b.message,
            created_at=b.created_at
        )
        for b in backups
    ]


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """恢复备份"""
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == backup_id)
    )
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")

    if backup.status != 1:
        raise HTTPException(status_code=400, detail="备份未完成或失败")

    restored = False

    # 恢复数据库
    db_backup = backup.file_path + ".db"
    if os.path.exists(db_backup):
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        # 先备份当前数据库
        if os.path.exists(db_path):
            shutil.copy2(db_path, db_path + ".before_restore")
        shutil.copy2(db_backup, db_path)
        restored = True

    # 恢复文件
    files_backup = backup.file_path + "_files.zip"
    if os.path.exists(files_backup):
        storage_path = settings.STORAGE_PATH
        # 清空当前文件目录
        if os.path.exists(storage_path):
            shutil.rmtree(storage_path)
        os.makedirs(storage_path, exist_ok=True)

        with zipfile.ZipFile(files_backup, 'r') as zipf:
            zipf.extractall(storage_path)
        restored = True

    if not restored:
        raise HTTPException(status_code=400, detail="未找到备份文件")

    await log_audit(
        db, current_user, "backup_restore", "system", backup.id,
        f"恢复{backup.backup_type}备份", request
    )

    return {"message": "恢复成功，请重启服务以生效"}


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """删除备份"""
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == backup_id)
    )
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")

    # 删除备份文件
    for ext in ['.db', '_files.zip']:
        path = backup.file_path + ext
        if os.path.exists(path):
            os.remove(path)

    await db.delete(backup)
    await db.commit()

    await log_audit(
        db, current_user, "backup_delete", "system", backup.id,
        f"删除{backup.backup_type}备份", request
    )

    return {"message": "备份已删除"}


@router.get("/download/{backup_id}")
async def download_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superuser),
):
    """下载备份文件"""
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == backup_id)
    )
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")

    # 打包所有备份文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_path = f"/tmp/backup_download_{timestamp}.zip"

    with zipfile.ZipFile(download_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for ext in ['.db', '_files.zip']:
            path = backup.file_path + ext
            if os.path.exists(path):
                zipf.write(path, os.path.basename(path))

    from fastapi.responses import FileResponse
    return FileResponse(
        path=download_path,
        filename=f"backup_{backup.backup_type}_{backup_id}.zip",
        media_type="application/zip"
    )


class ScheduleConfig(BaseModel):
    enabled: bool = True
    hour: int = 2
    minute: int = 0


@router.get("/schedule")
async def get_schedule(
    current_user: User = Depends(get_superuser),
):
    """获取定时备份配置"""
    return get_backup_schedule()


@router.post("/schedule")
async def set_schedule(
    config: ScheduleConfig,
    current_user: User = Depends(get_superuser),
):
    """设置定时备份配置"""
    update_backup_schedule(config.hour, config.minute, config.enabled)
    return {
        "message": f"定时备份已{'启用' if config.enabled else '禁用'}",
        "schedule": get_backup_schedule()
    }
