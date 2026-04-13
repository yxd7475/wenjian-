"""
审计日志 API 路由
"""
import io
import csv
from typing import Optional, List
from urllib.parse import quote
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, AuditLog
from app.schemas import AuditLogResponse, AuditLogListResponse
from app.api.deps import get_current_user, require_permission
from app.utils.timezone import get_beijing_time, utc_to_beijing

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])

# 操作类型中文翻译
ACTION_NAMES = {
    "login": "登录",
    "logout": "登出",
    "password_change": "修改密码",
    "password_reset": "重置密码",
    "folder_create": "创建文件夹",
    "folder_delete": "删除文件夹",
    "folder_rename": "重命名文件夹",
    "file_upload": "上传文件",
    "file_download": "下载文件",
    "file_delete": "删除文件",
    "file_batch_delete": "批量删除文件",
    "file_rename": "重命名文件",
    "file_move": "移动文件",
    "file_copy": "复制文件",
    "file_restore": "恢复文件",
    "file_permanent_delete": "永久删除文件",
    "trash_empty": "清空回收站",
    "file_share": "分享文件",
    "share_enable": "启用分享",
    "share_disable": "禁用分享",
    "share_delete": "删除分享",
    "user_create": "创建用户",
    "user_delete": "删除用户",
    "user_update": "更新用户",
    "user_status_toggle": "切换用户状态",
    "version_rollback": "版本回滚",
    "version_delete": "删除版本",
    "backup_create": "创建备份",
    "backup_restore": "恢复备份",
    "backup_delete": "删除备份",
}

# 目标类型中文翻译
TARGET_TYPE_NAMES = {
    "user": "用户",
    "file": "文件",
    "folder": "文件夹",
    "system": "系统",
    "share": "分享",
}


def get_action_name(action: str) -> str:
    """获取操作的中文翻译"""
    return ACTION_NAMES.get(action, action)


def get_target_type_name(target_type: str) -> str:
    """获取目标类型的中文翻译"""
    if not target_type:
        return ""
    return TARGET_TYPE_NAMES.get(target_type, target_type)


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志列表"""
    query = select(AuditLog)

    # 筛选条件
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.where(AuditLog.created_at >= start_datetime)
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.where(AuditLog.created_at <= end_datetime)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(AuditLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for log in logs:
        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=log.username,
            action=log.action,
            action_name=get_action_name(log.action),
            target_type=log.target_type,
            target_id=log.target_id,
            target_name=log.target_name,
            ip=log.ip,
            result=log.result,
            detail=log.detail,
            created_at=utc_to_beijing(log.created_at)
        ))

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/actions", response_model=List[dict])
async def get_action_types(
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """获取所有操作类型（含中文翻译）"""
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.all()]
    return [{"code": action, "name": get_action_name(action)} for action in actions]


@router.get("/stats/summary")
async def get_audit_summary(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """获取审计统计摘要"""
    start_date = get_beijing_time() - timedelta(days=days)

    # 总操作数
    result = await db.execute(
        select(func.count()).where(AuditLog.created_at >= start_date)
    )
    total_operations = result.scalar()

    # 成功/失败统计
    result = await db.execute(
        select(AuditLog.result, func.count())
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.result)
    )
    result_stats = {str(row[0]): row[1] for row in result.all()}

    # 按操作类型统计
    result = await db.execute(
        select(AuditLog.action, func.count())
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
        .limit(10)
    )
    action_stats = [{"action": row[0], "action_name": get_action_name(row[0]), "count": row[1]} for row in result.all()]

    # 按用户统计
    result = await db.execute(
        select(AuditLog.username, func.count())
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.username)
        .order_by(func.count().desc())
        .limit(10)
    )
    user_stats = [{"username": row[0], "count": row[1]} for row in result.all()]

    return {
        "period_days": days,
        "total_operations": total_operations,
        "success_count": result_stats.get("True", 0),
        "failure_count": result_stats.get("False", 0),
        "by_action": action_stats,
        "by_user": user_stats,
    }


@router.get("/export")
async def export_audit_logs(
    action: Optional[str] = Query(None, description="操作类型"),
    target_type: Optional[str] = Query(None, description="目标类型"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """导出审计日志为CSV文件"""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    # 筛选条件
    if action:
        query = query.where(AuditLog.action == action)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if start_date:
        # Convert date to datetime at start of day
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.where(AuditLog.created_at >= start_datetime)
    if end_date:
        # Convert date to datetime at end of day
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.where(AuditLog.created_at <= end_datetime)

    result = await db.execute(query)
    logs = result.scalars().all()

    # 创建CSV内容
    output = io.StringIO()
    # 使用 utf-8-sig 编码以支持中文
    writer = csv.writer(output)

    # 写入表头
    writer.writerow([
        "ID", "用户名", "操作类型", "目标类型", "目标ID",
        "目标名称", "IP地址", "结果", "操作时间"
    ])

    # 写入数据
    for log in logs:
        writer.writerow([
            log.id,
            log.username or "",
            get_action_name(log.action),
            get_target_type_name(log.target_type),
            log.target_id or "",
            log.target_name or "",
            log.ip or "",
            "成功" if log.result else "失败",
            utc_to_beijing(log.created_at).strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
        ])

    # 生成文件名
    filename_parts = ["审计日志"]
    if action:
        filename_parts.append(get_action_name(action))
    if start_date:
        filename_parts.append(start_date.strftime("%Y%m%d"))
    if end_date:
        filename_parts.append(end_date.strftime("%Y%m%d"))
    filename = "_".join(filename_parts) + ".csv"

    # 返回CSV文件
    output.seek(0)
    # 对中文文件名进行URL编码（RFC 5987）
    encoded_filename = quote(filename)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )
