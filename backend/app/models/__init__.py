"""
模型初始化
"""
from app.models.models import (
    User,
    Department,
    Role,
    Permission,
    RolePermission,
    Folder,
    File,
    FileVersion,
    FilePermission,
    AuditLog,
    UploadTask,
)

__all__ = [
    "User",
    "Department",
    "Role",
    "Permission",
    "RolePermission",
    "Folder",
    "File",
    "FileVersion",
    "FilePermission",
    "AuditLog",
    "UploadTask",
]
