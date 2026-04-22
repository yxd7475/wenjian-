"""
数据库模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.utils.timezone import get_beijing_time


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    real_name = Column(String(50), comment="真实姓名")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    unique_id = Column(String(10), unique=True, index=True, nullable=True, comment="用户唯一标识码")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, comment="部门ID")
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, comment="角色ID")
    status = Column(Boolean, default=True, comment="状态：启用/禁用")
    is_superuser = Column(Boolean, default=False, comment="是否超级管理员")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, comment="更新时间")

    # 关联
    department = relationship("Department", back_populates="users")
    role = relationship("Role", back_populates="users")


class Department(Base):
    """部门表"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="部门名称")
    code = Column(String(50), unique=True, comment="部门代码")
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True, comment="上级部门ID")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(Boolean, default=True, comment="状态")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    users = relationship("User", back_populates="department")
    children = relationship("Department", backref="parent", remote_side=[id])


class Role(Base):
    """角色表"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="角色名称")
    code = Column(String(50), unique=True, nullable=False, comment="角色代码")
    description = Column(Text, nullable=True, comment="描述")
    is_system = Column(Boolean, default=False, comment="是否系统内置角色")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    users = relationship("User", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    """权限表"""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False, comment="权限代码")
    name = Column(String(100), nullable=False, comment="权限名称")
    category = Column(String(50), comment="权限分类")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime, default=get_beijing_time)


class RolePermission(Base):
    """角色权限关联表"""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission")


class Folder(Base):
    """文件夹表"""
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), nullable=False, comment="所属空间ID")
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True, comment="父文件夹ID")
    name = Column(String(255), nullable=False, comment="文件夹名称")
    path = Column(String(1000), comment="完整路径")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="所有者ID")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    space = relationship("Space")
    owner = relationship("User")
    children = relationship("Folder", backref="parent", remote_side=[id])
    files = relationship("File", back_populates="folder")


class File(Base):
    """文件表"""
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), nullable=False, comment="所属空间ID")
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True, comment="文件夹ID")
    origin_name = Column(String(255), nullable=False, comment="原始文件名")
    stored_name = Column(String(255), nullable=False, comment="存储文件名")
    storage_path = Column(String(1000), nullable=False, comment="存储路径")
    ext = Column(String(20), comment="文件扩展名")
    mime_type = Column(String(100), comment="MIME类型")
    size = Column(BigInteger, default=0, comment="文件大小(字节)")
    hash_sha256 = Column(String(64), comment="文件SHA256哈希")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="上传者ID")
    version_no = Column(Integer, default=1, comment="版本号")
    status = Column(Integer, default=1, comment="状态：1正常 2回收站 3已删除")
    remark = Column(Text, nullable=True, comment="备注")
    extra_json = Column(JSON, nullable=True, comment="扩展信息")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    category_id = Column(Integer, ForeignKey("file_categories.id"), nullable=True, comment="分类ID")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    space = relationship("Space")
    folder = relationship("Folder", back_populates="files")
    owner = relationship("User")
    versions = relationship("FileVersion", back_populates="file")
    category = relationship("FileCategory")


class FileVersion(Base):
    """文件版本表"""
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, comment="文件ID")
    version_no = Column(Integer, nullable=False, comment="版本号")
    storage_path = Column(String(1000), nullable=False, comment="存储路径")
    size = Column(BigInteger, default=0, comment="文件大小")
    hash_sha256 = Column(String(64), comment="文件哈希")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    file = relationship("File", back_populates="versions")
    creator = relationship("User")


class FilePermission(Base):
    """文件权限表"""
    __tablename__ = "file_permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, comment="文件ID")
    subject_type = Column(String(20), nullable=False, comment="主体类型：user/role/dept")
    subject_id = Column(Integer, nullable=False, comment="主体ID")
    can_view = Column(Boolean, default=True, comment="可查看")
    can_upload = Column(Boolean, default=False, comment="可上传")
    can_download = Column(Boolean, default=True, comment="可下载")
    can_delete = Column(Boolean, default=False, comment="可删除")
    can_manage = Column(Boolean, default=False, comment="可管理")
    created_at = Column(DateTime, default=get_beijing_time)


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="用户ID")
    username = Column(String(50), comment="用户名")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), comment="目标类型")
    target_id = Column(Integer, comment="目标ID")
    target_name = Column(String(255), comment="目标名称")
    ip = Column(String(50), comment="IP地址")
    user_agent = Column(String(500), comment="User-Agent")
    result = Column(Boolean, default=True, comment="操作结果")
    detail = Column(JSON, nullable=True, comment="详细信息")
    created_at = Column(DateTime, default=get_beijing_time, index=True)

    # 关联
    user = relationship("User")


class UploadTask(Base):
    """上传任务表"""
    __tablename__ = "upload_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_size = Column(BigInteger, default=0, comment="文件大小")
    chunk_total = Column(Integer, default=1, comment="总分片数")
    chunk_uploaded = Column(Integer, default=0, comment="已上传分片数")
    chunk_size = Column(Integer, default=5242880, comment="分片大小")
    upload_id = Column(String(100), unique=True, comment="上传ID")
    status = Column(Integer, default=0, comment="状态：0等待 1上传中 2完成 3失败")
    storage_path = Column(String(1000), comment="存储路径")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    user = relationship("User")


class FileShare(Base):
    """文件分享表"""
    __tablename__ = "file_shares"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, comment="文件ID")
    share_code = Column(String(32), unique=True, nullable=False, comment="分享码")
    password = Column(String(20), nullable=True, comment="访问密码")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, comment="创建者ID")
    expire_at = Column(DateTime, nullable=True, comment="过期时间")
    max_downloads = Column(Integer, default=0, comment="最大下载次数，0表示不限")
    download_count = Column(Integer, default=0, comment="已下载次数")
    is_active = Column(Boolean, default=True, comment="是否有效")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    file = relationship("File")
    creator = relationship("User")


class BackupRecord(Base):
    """备份记录表"""
    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    backup_type = Column(String(20), nullable=False, comment="备份类型：full/data/files")
    file_path = Column(String(500), nullable=False, comment="备份文件路径")
    file_size = Column(BigInteger, default=0, comment="文件大小")
    status = Column(Integer, default=0, comment="状态：0进行中 1成功 2失败")
    message = Column(Text, nullable=True, comment="备注信息")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    creator = relationship("User")


class AuditAlert(Base):
    """审计告警表"""
    __tablename__ = "audit_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False, comment="告警类型")
    severity = Column(String(20), default="warning", comment="严重级别：info/warning/danger")
    title = Column(String(255), nullable=False, comment="告警标题")
    content = Column(Text, nullable=True, comment="告警内容")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="相关用户ID")
    username = Column(String(50), comment="相关用户名")
    is_read = Column(Boolean, default=False, comment="是否已读")
    is_handled = Column(Boolean, default=False, comment="是否已处理")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    user = relationship("User")


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, comment="配置键")
    config_value = Column(Text, nullable=True, comment="配置值")
    config_type = Column(String(20), default="string", comment="值类型：string/number/boolean/json")
    description = Column(String(255), nullable=True, comment="配置说明")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)


class Space(Base):
    """空间表"""
    __tablename__ = "spaces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="空间名称")
    space_type = Column(String(20), nullable=False, comment="空间类型：admin/personal/group")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="所有者ID（个人空间对应用户）")
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True, comment="群组ID（群组空间关联群组）")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(Boolean, default=True, comment="状态")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    owner = relationship("User", foreign_keys=[owner_id])
    group = relationship("Group", back_populates="space", foreign_keys=[group_id])


class Group(Base):
    """群组表"""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="群组名称")
    description = Column(Text, nullable=True, comment="描述")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="群主ID")
    invite_code = Column(String(32), unique=True, nullable=True, comment="邀请码")
    is_public_join = Column(Boolean, default=False, comment="是否公开加入")
    status = Column(Boolean, default=True, comment="状态")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("GroupMember", back_populates="group")
    space = relationship("Space", back_populates="group", uselist=False)


class GroupMember(Base):
    """群组成员表"""
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, comment="群组ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    role = Column(String(20), nullable=False, default="member", comment="角色：owner/manager/member/viewer")
    join_status = Column(String(20), nullable=False, default="active", comment="状态：invited/active/rejected/left")
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="邀请人ID")
    joined_at = Column(DateTime, default=get_beijing_time, comment="加入时间")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    group = relationship("Group", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[invited_by])


class Invitation(Base):
    """邀请表"""
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, comment="群组ID")
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="邀请人ID")
    invitee_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="被邀请人ID")
    invite_code = Column(String(32), nullable=True, comment="邀请码")
    status = Column(String(20), nullable=False, default="pending", comment="状态：pending/accepted/rejected/expired")
    expire_at = Column(DateTime, nullable=True, comment="过期时间")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    group = relationship("Group")
    inviter = relationship("User", foreign_keys=[inviter_id])
    invitee = relationship("User", foreign_keys=[invitee_id])


class Friendship(Base):
    """好友关系表"""
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="发起人ID")
    addressee_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="接收人ID")
    status = Column(String(20), nullable=False, default="pending", comment="状态：pending/accepted/rejected/blocked")
    message = Column(String(200), nullable=True, comment="申请附言")
    created_at = Column(DateTime, default=get_beijing_time)
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联
    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])

    # 联合唯一约束
    __table_args__ = (
        UniqueConstraint('requester_id', 'addressee_id', name='unique_friendship'),
    )


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="发送者ID")
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="接收者ID")
    content = Column(Text, nullable=False, comment="消息内容")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class GroupChatMessage(Base):
    """群组聊天消息表"""
    __tablename__ = "group_chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, comment="群组ID")
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="发送者ID")
    message_type = Column(String(20), default="text", comment="消息类型：text/file/image")
    content = Column(Text, nullable=False, comment="消息内容")
    # 文件相关字段
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True, comment="关联文件ID")
    file_name = Column(String(255), nullable=True, comment="文件名称")
    file_size = Column(BigInteger, nullable=True, comment="文件大小")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    group = relationship("Group")
    sender = relationship("User")
    file = relationship("File")


class Notification(Base):
    """系统通知表"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="接收用户ID")
    notification_type = Column(String(50), nullable=False, comment="通知类型：friend_request/group_invite/system/file_share/chat")
    title = Column(String(255), nullable=False, comment="通知标题")
    content = Column(Text, nullable=True, comment="通知内容")
    data = Column(JSON, nullable=True, comment="附加数据")
    related_id = Column(Integer, nullable=True, comment="关联ID")
    related_type = Column(String(50), nullable=True, comment="关联类型：group/friendship/file等")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=get_beijing_time)

    # 关联
    user = relationship("User")


class FileCategory(Base):
    """文件分类表"""
    __tablename__ = "file_categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="分类名称")
    icon = Column(String(50), nullable=True, comment="图标名称")
    color = Column(String(20), nullable=True, comment="颜色")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=get_beijing_time)
