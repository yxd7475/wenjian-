"""
数据库初始化脚本
"""
import asyncio
import os
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine, AsyncSessionLocal, Base
from app.models.models import User, Role, Permission, Department, RolePermission
from app.core.security import get_password_hash


async def create_tables():
    """创建数据表"""
    # 确保数据目录存在
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] 数据表创建完成")


async def init_permissions(session: AsyncSession):
    """初始化权限数据"""
    permissions_data = [
        # 文件权限
        {"code": "file:view", "name": "查看文件", "category": "文件"},
        {"code": "file:upload", "name": "上传文件", "category": "文件"},
        {"code": "file:download", "name": "下载文件", "category": "文件"},
        {"code": "file:delete", "name": "删除文件", "category": "文件"},
        {"code": "file:rename", "name": "重命名文件", "category": "文件"},
        {"code": "file:move", "name": "移动文件", "category": "文件"},
        {"code": "file:copy", "name": "复制文件", "category": "文件"},
        {"code": "file:share", "name": "分享文件", "category": "文件"},
        # 文件夹权限
        {"code": "folder:create", "name": "创建文件夹", "category": "文件夹"},
        {"code": "folder:view", "name": "查看文件夹", "category": "文件夹"},
        {"code": "folder:delete", "name": "删除文件夹", "category": "文件夹"},
        {"code": "folder:rename", "name": "重命名文件夹", "category": "文件夹"},
        # 用户管理权限
        {"code": "user:view", "name": "查看用户", "category": "用户管理"},
        {"code": "user:create", "name": "创建用户", "category": "用户管理"},
        {"code": "user:update", "name": "更新用户", "category": "用户管理"},
        {"code": "user:delete", "name": "删除用户", "category": "用户管理"},
        # 系统管理权限
        {"code": "system:config", "name": "系统配置", "category": "系统"},
        {"code": "system:audit", "name": "审计日志", "category": "系统"},
        {"code": "system:backup", "name": "数据备份", "category": "系统"},
    ]

    for perm_data in permissions_data:
        result = await session.execute(
            select(Permission).where(Permission.code == perm_data["code"])
        )
        if not result.scalar_one_or_none():
            perm = Permission(**perm_data)
            session.add(perm)

    await session.commit()
    print("[OK] 权限数据初始化完成")


async def init_roles(session: AsyncSession):
    """初始化角色数据"""
    roles_data = [
        {"name": "超级管理员", "code": "super_admin", "description": "系统超级管理员，拥有所有权限", "is_system": True},
        {"name": "管理员", "code": "admin", "description": "普通管理员，可管理用户和文件", "is_system": True},
        {"name": "普通用户", "code": "user", "description": "普通用户，可上传下载文件", "is_system": True},
        {"name": "访客", "code": "guest", "description": "访客用户，只能查看和下载", "is_system": True},
    ]

    for role_data in roles_data:
        result = await session.execute(
            select(Role).where(Role.code == role_data["code"])
        )
        if not result.scalar_one_or_none():
            role = Role(**role_data)
            session.add(role)

    await session.commit()
    print("[OK] 角色数据初始化完成")


async def init_role_permissions(session: AsyncSession):
    """初始化角色权限关联"""
    # 获取所有权限
    result = await session.execute(select(Permission))
    permissions = {p.code: p.id for p in result.scalars().all()}

    # 获取所有角色
    result = await session.execute(select(Role))
    roles = {r.code: r.id for r in result.scalars().all()}

    # 角色权限映射
    role_permission_map = {
        "super_admin": list(permissions.keys()),  # 所有权限
        "admin": [
            "file:view", "file:upload", "file:download", "file:delete", "file:rename", "file:move", "file:copy", "file:share",
            "folder:create", "folder:view", "folder:delete", "folder:rename",
            "user:view", "user:create", "user:update",
            "system:audit",
        ],
        "user": [
            "file:view", "file:upload", "file:download", "file:rename",
            "folder:create", "folder:view", "folder:rename",
        ],
        "guest": [
            "file:view", "file:download",
            "folder:view",
        ],
    }

    for role_code, perm_codes in role_permission_map.items():
        if role_code not in roles:
            continue
        role_id = roles[role_code]
        for perm_code in perm_codes:
            if perm_code not in permissions:
                continue
            perm_id = permissions[perm_code]

            # 检查是否已存在
            result = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == perm_id
                )
            )
            if not result.scalar_one_or_none():
                rp = RolePermission(role_id=role_id, permission_id=perm_id)
                session.add(rp)

    await session.commit()
    print("[OK] 角色权限关联初始化完成")


async def init_departments(session: AsyncSession):
    """初始化部门数据"""
    dept_data = [
        {"name": "总公司", "code": "hq", "description": "公司总部"},
        {"name": "技术部", "code": "tech", "description": "技术研发部门"},
        {"name": "行政部", "code": "admin_dept", "description": "行政部门"},
        {"name": "财务部", "code": "finance", "description": "财务部门"},
    ]

    for dept in dept_data:
        result = await session.execute(
            select(Department).where(Department.code == dept["code"])
        )
        if not result.scalar_one_or_none():
            session.add(Department(**dept))

    await session.commit()
    print("[OK] 部门数据初始化完成")


async def init_superuser(session: AsyncSession):
    """初始化超级管理员账号"""
    result = await session.execute(
        select(User).where(User.username == "admin")
    )
    if not result.scalar_one_or_none():
        # 获取超级管理员角色
        result = await session.execute(
            select(Role).where(Role.code == "super_admin")
        )
        role = result.scalar_one_or_none()

        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            real_name="系统管理员",
            role_id=role.id if role else None,
            is_superuser=True,
            status=True,
        )
        session.add(admin)
        await session.commit()
        print("[OK] 超级管理员账号创建完成 (用户名: admin, 密码: admin123)")
    else:
        print("[OK] 超级管理员账号已存在")


async def init_db():
    """数据库初始化主函数"""
    print("开始初始化数据库...")

    # 创建表
    await create_tables()

    # 初始化基础数据
    async with AsyncSessionLocal() as session:
        await init_permissions(session)
        await init_roles(session)
        await init_role_permissions(session)
        await init_departments(session)
        await init_superuser(session)

    print("\n数据库初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_db())
