"""
定时备份调度器
"""
import asyncio
import os
import shutil
import zipfile
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.config import settings
from app.models.models import BackupRecord
from app.utils.timezone import get_beijing_time

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def run_scheduled_backup():
    """执行定时备份"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # 创建备份记录
            backup = BackupRecord(
                backup_type="full",
                file_path="",
                file_size=0,
                status=0,  # 进行中
                created_by=1  # 系统自动备份
            )
            db.add(backup)
            await db.commit()
            await db.refresh(backup)

            # 创建备份目录
            backup_dir = os.path.join(settings.STORAGE_PATH, "..", "backups")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"auto_backup_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_filename)

            # 数据库备份
            db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
            if os.path.exists(db_path):
                db_backup_path = backup_path + ".db"
                shutil.copy2(db_path, db_backup_path)

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
                if f.startswith(f"auto_backup_{timestamp[:15]}"):
                    total_size += os.path.getsize(os.path.join(backup_dir, f))

            backup.file_path = backup_path
            backup.file_size = total_size
            backup.status = 1  # 成功
            backup.message = "定时备份完成"
            await db.commit()

            # 清理超过30天的自动备份
            await cleanup_old_backups(db, backup_dir)

        except Exception as e:
            backup.status = 2  # 失败
            backup.message = str(e)
            await db.commit()


async def cleanup_old_backups(db, backup_dir):
    """清理超过30天的自动备份"""
    import time
    cutoff_time = time.time() - (30 * 24 * 60 * 60)  # 30天前

    for filename in os.listdir(backup_dir):
        if filename.startswith("auto_backup_"):
            filepath = os.path.join(backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff_time:
                os.remove(filepath)

    # 删除数据库中超过30天的自动备份记录
    cutoff_date = get_beijing_time() - __import__('datetime').timedelta(days=30)
    result = await db.execute(
        select(BackupRecord).where(
            BackupRecord.created_at < cutoff_date,
            BackupRecord.backup_type == "full",
            BackupRecord.message == "定时备份完成"
        )
    )
    old_backups = result.scalars().all()
    for old_backup in old_backups:
        await db.delete(old_backup)
    await db.commit()


def setup_scheduler():
    """设置定时备份调度器"""
    # 默认每天凌晨2点执行备份
    scheduler.add_job(
        run_scheduled_backup,
        CronTrigger(hour=2, minute=0),
        id="daily_backup",
        replace_existing=True
    )
    scheduler.start()


def update_backup_schedule(hour: int, minute: int, enabled: bool = True):
    """更新备份调度时间"""
    if scheduler.get_job("daily_backup"):
        scheduler.remove_job("daily_backup")

    if enabled:
        scheduler.add_job(
            run_scheduled_backup,
            CronTrigger(hour=hour, minute=minute),
            id="daily_backup",
            replace_existing=True
        )


def get_backup_schedule():
    """获取当前备份调度配置"""
    try:
        job = scheduler.get_job("daily_backup")
        if job:
            trigger = job.trigger
            # CronTrigger fields: year, month, day, week, day_of_week, hour, minute, second
            hour = 2
            minute = 0
            if hasattr(trigger, 'fields'):
                # fields[5] is hour, fields[6] is minute
                if len(trigger.fields) > 5:
                    hour_field = trigger.fields[5]
                    if hasattr(hour_field, 'expressions') and hour_field.expressions:
                        hour = hour_field.expressions[0].start
                if len(trigger.fields) > 6:
                    minute_field = trigger.fields[6]
                    if hasattr(minute_field, 'expressions') and minute_field.expressions:
                        minute = minute_field.expressions[0].start
            return {
                "enabled": True,
                "hour": hour,
                "minute": minute,
            }
        return {"enabled": False, "hour": 2, "minute": 0}
    except Exception:
        return {"enabled": False, "hour": 2, "minute": 0}
