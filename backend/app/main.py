"""
局域网文件共享系统 - FastAPI 主应用
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api import auth_router, users_router, files_router, audit_router, roles_router
from app.api.dashboard import router as dashboard_router
from app.api.versions import router as versions_router
from app.api.shares import router as shares_router
from app.api.backup import router as backup_router
from app.api.alerts import router as alerts_router
from app.api.chunk_upload import router as chunk_upload_router
from app.api.spaces import router as spaces_router
from app.api.groups import router as groups_router
from app.api.invitations import router as invitations_router
from app.api.friends import router as friends_router
from app.api.chat import router as chat_router
from app.api.group_chat import router as group_chat_router
from app.api.notifications import router as notifications_router
from app.utils.scheduler import setup_scheduler
from app.core.notifications import manager
from app.core.security import decode_access_token

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("正在启动应用...")

    # 创建必要的目录
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    os.makedirs(settings.UPLOAD_TEMP_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(settings.LOG_FILE) if settings.LOG_FILE else "./logs", exist_ok=True)

    # 初始化数据库
    from app.db.init_db import init_db
    import asyncio
    await init_db()

    # 启动定时备份调度器
    setup_scheduler()
    logger.info("定时备份调度器已启动")

    logger.info(f"应用已启动: http://{settings.HOST}:{settings.PORT}")

    yield

    # 关闭时
    logger.info("应用正在关闭...")


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    description="局域网文件共享系统 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "error_code": "INTERNAL_ERROR"},
    )


# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(roles_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(versions_router, prefix="/api")
app.include_router(shares_router, prefix="/api")
app.include_router(backup_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(chunk_upload_router, prefix="/api")
app.include_router(spaces_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(invitations_router, prefix="/api")
app.include_router(friends_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(group_chat_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "app_name": settings.APP_NAME}


# WebSocket 端点
@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket 连接端点"""
    # 验证token
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = int(user_id)

    # 建立连接
    await manager.connect(websocket, user_id)
    try:
        while True:
            # 接收消息（心跳或其他）
            data = await websocket.receive_text()
            # 处理心跳
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                # 其他消息原样返回确认
                await websocket.send_json({"type": "ack", "message": "received"})
    except Exception:
        pass
    finally:
        manager.disconnect(websocket, user_id)


# 根路径
@app.get("/")
async def root():
    return {
        "message": f"欢迎使用 {settings.APP_NAME}",
        "docs": "/api/docs",
        "health": "/health",
    }


# 挂载静态文件目录 (用于文件预览)
if os.path.exists(settings.STORAGE_PATH):
    app.mount("/storage", StaticFiles(directory=settings.STORAGE_PATH), name="storage")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
