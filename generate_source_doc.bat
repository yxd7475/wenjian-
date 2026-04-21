@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set OUTPUT=源程序文档.txt
set FRONTEND_SRC=C:\Users\HASEE\Desktop\共享文件\frontend\src
set BACKEND_SRC=C:\Users\HASEE\Desktop\共享文件\backend\app

echo 正在生成源程序文档...
echo. > %OUTPUT%

echo ======================================== >> %OUTPUT%
echo       局域网文件共享系统 - 源程序 >> %OUTPUT%
echo ======================================== >> %OUTPUT%
echo. >> %OUTPUT%

echo [1/2] 整理后端代码...
for /r "%BACKEND_SRC%" %%f in (*.py) do (
    echo. >> %OUTPUT%
    echo ========== 文件: %%~pnxf ========== >> %OUTPUT%
    type "%%f" >> %OUTPUT%
    echo. >> %OUTPUT%
)

echo [2/2] 整理前端代码...
for /r "%FRONTEND_SRC%" %%f in (*.vue *.js) do (
    echo. >> %OUTPUT%
    echo ========== 文件: %%~pnxf ========== >> %OUTPUT%
    type "%%f" >> %OUTPUT%
    echo. >> %OUTPUT%
)

echo 完成！输出文件: %OUTPUT%
pause
