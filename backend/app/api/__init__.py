"""
API路由初始化
"""
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.files import router as files_router
from app.api.audit import router as audit_router

__all__ = [
    "auth_router",
    "users_router",
    "files_router",
    "audit_router",
]
