"""
局域网文件共享系统 - 核心配置
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os

# 获取项目根目录（backend 目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "局域网文件共享系统"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production-please"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/share.db"

    # Redis配置 (可选)
    REDIS_URL: Optional[str] = None

    # 文件存储配置 - 使用绝对路径
    STORAGE_PATH: str = os.path.join(BASE_DIR, "data", "storage")
    UPLOAD_TEMP_PATH: str = os.path.join(BASE_DIR, "data", "temp")
    MAX_UPLOAD_SIZE: int = 524288000  # 500MB
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,bmp,webp,pdf,txt,md,doc,docx,xls,xlsx,ppt,pptx,zip,rar,7z,mp3,mp4,avi,mov"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = os.path.join(BASE_DIR, "logs", "app.log")

    @property
    def allowed_extensions_list(self) -> list:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
