@echo off
chcp 65001 >nul
title AutoClip 后端服务

echo ========================================
echo    AutoClip 后端启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 检查虚拟环境...
if not exist "venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行环境安装
    pause
    exit /b 1
)
echo [OK] 虚拟环境存在

echo.
echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat
echo [OK] 虚拟环境已激活

echo.
echo [3/4] 检查端口8090...
netstat -ano | findstr ":8090" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [警告] 端口8090已被占用！
    echo.
    echo 请先停止现有服务：
    echo   - 关闭所有 AutoClip 相关窗口
    echo   - 或者运行 stop_autoclip.bat
    echo.
    pause
    exit /b 1
)
echo [OK] 端口8090可用

echo.
echo [4/4] 启动后端服务...
echo.
echo ========================================
echo    后端启动中，请等待...
echo ========================================
echo.

REM 启动后端（使用 python -m uvicorn 而不是 uvicorn 命令）
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8090

echo.
echo 后端服务已关闭
pause
