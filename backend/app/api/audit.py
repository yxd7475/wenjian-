"""
审计日志 API 路由
"""
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, AuditLog
from app.schemas import AuditLogResponse, AuditLogListResponse
from app.api.deps import get_current_user, require_permission

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
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
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(AuditLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/actions", response_model=List[str])
async def get_action_types(
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """获取所有操作类型"""
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.all()]
    return actions


@router.get("/stats/summary")
async def get_audit_summary(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(require_permission("system:audit")),
    db: AsyncSession = Depends(get_db),
):
    """获取审计统计摘要"""
    start_date = datetime.utcnow() - timedelta(days=days)

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
    action_stats = [{"action": row[0], "count": row[1]} for row in result.all()]

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
