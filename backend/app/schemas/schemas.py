"""
Pydantic Schemas - 数据验证和序列化模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


# ==================== 角色相关 ====================
class RoleBase(BaseModel):
    name: str = Field(..., max_length=50, description="角色名称")
    code: str = Field(..., max_length=50, description="角色代码")
    description: Optional[str] = None


class RoleResponse(RoleBase):
    id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 用户相关 ====================
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    real_name: Optional[str] = Field(None, max_length=50, description="真实姓名")
    email: Optional[EmailStr] = Field(None, description="邮箱")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    department_id: Optional[int] = Field(None, description="部门ID")
    role_id: Optional[int] = Field(None, description="角色ID")


class UserUpdate(BaseModel):
    real_name: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None


class UserResponse(UserBase):
    id: int
    unique_id: Optional[str] = None
    department_id: Optional[int]
    role_id: Optional[int]
    role: Optional[RoleResponse] = None
    status: bool
    is_superuser: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


# ==================== 认证相关 ====================
class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChange(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class PasswordReset(BaseModel):
    user_id: int = Field(..., description="用户ID")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# ==================== 部门相关 ====================
class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=100, description="部门名称")
    code: Optional[str] = Field(None, max_length=50, description="部门代码")
    parent_id: Optional[int] = Field(None, description="上级部门ID")
    description: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[int] = None
    description: Optional[str] = None


class DepartmentResponse(DepartmentBase):
    id: int
    status: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DepartmentTree(DepartmentResponse):
    children: List["DepartmentTree"] = []


# ==================== 角色相关 ====================
class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


# ==================== 文件夹相关 ====================
class FolderBase(BaseModel):
    name: str = Field(..., max_length=255, description="文件夹名称")
    parent_id: Optional[int] = Field(None, description="父文件夹ID")
    space_id: Optional[int] = Field(None, description="所属空间ID")


class FolderCreate(FolderBase):
    pass


class FolderRename(BaseModel):
    name: str = Field(..., max_length=255, description="新名称")


class FolderResponse(FolderBase):
    id: int
    space_id: Optional[int]
    path: Optional[str]
    owner_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderTree(FolderResponse):
    children: Optional[List["FolderTree"]] = None


# ==================== 文件相关 ====================
class FileBase(BaseModel):
    origin_name: str = Field(..., max_length=255, description="原始文件名")
    remark: Optional[str] = Field(None, description="备注")


class FileOwnerInfo(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None

    class Config:
        from_attributes = True


class FileCategoryInfo(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None

    class Config:
        from_attributes = True


class FileResponse(BaseModel):
    id: int
    space_id: Optional[int]
    folder_id: Optional[int]
    origin_name: str
    ext: Optional[str]
    mime_type: Optional[str]
    size: int
    owner_id: int
    owner: Optional[FileOwnerInfo] = None
    category_id: Optional[int] = None
    category: Optional[FileCategoryInfo] = None
    version_no: int
    status: int
    remark: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    items: List[FileResponse]
    total: int
    page: int
    page_size: int


class FileMove(BaseModel):
    target_folder_id: int = Field(..., description="目标文件夹ID")


class FileCopy(BaseModel):
    target_folder_id: int = Field(..., description="目标文件夹ID")
    new_name: Optional[str] = Field(None, description="新文件名")


# ==================== 上传相关 ====================
class UploadInit(BaseModel):
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., ge=0, description="文件大小")
    chunk_size: Optional[int] = Field(5242880, description="分片大小，默认5MB")
    folder_id: Optional[int] = Field(None, description="目标文件夹ID")


class UploadChunk(BaseModel):
    upload_id: str = Field(..., description="上传ID")
    chunk_index: int = Field(..., ge=0, description="分片索引")
    chunk_total: int = Field(..., ge=1, description="总分片数")


class UploadComplete(BaseModel):
    upload_id: str = Field(..., description="上传ID")


class UploadTaskResponse(BaseModel):
    id: int
    upload_id: str
    file_name: str
    file_size: int
    chunk_total: int
    chunk_uploaded: int
    status: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 审计日志相关 ====================
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    action_name: Optional[str] = None  # 中文操作名称
    target_type: Optional[str]
    target_id: Optional[int]
    target_name: Optional[str]
    ip: Optional[str]
    result: bool
    detail: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ==================== 通用响应 ====================
class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
