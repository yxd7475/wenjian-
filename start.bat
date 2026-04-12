@echo off
echo ========================================
echo   局域网文件共享系统 - 启动脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/4] 安装后端依赖...
cd backend
pip install -r requirements.txt -q

echo [2/4] 配置环境变量...
if not exist .env copy .env.example .env

echo [3/4] 安装前端依赖...
cd ..\frontend
call npm install

echo [4/4] 启动服务...
echo.
echo 后端服务: http://localhost:8088
echo 前端服务: http://localhost:3088
echo API文档:  http://localhost:8088/api/docs
echo.

:: 启动后端 (后台运行)
cd ..\backend
start /b python -m uvicorn app.main:app --host 0.0.0.0 --port 8088

:: 启动前端
cd ..\frontend
call npm run dev

pause
