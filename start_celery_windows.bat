@echo off
chcp 65001 >nul
echo ========================================
echo   AutoClip Celery Worker (Windows版)
echo ========================================
echo.
echo 启动模式: Eventlet (多线程)
echo 说明: 此模式兼容Windows，支持多核处理
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在，请先创建虚拟环境
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo 检查 Redis 连接...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [警告] Redis 未运行，正在启动...
    redis-server --daemonize yes
    timeout /t 2 /nobreak >nul
)

echo.
echo 启动 Celery Worker (Eventlet 模式)...
echo.
python -m celery -A backend.core.celery_app worker --loglevel=info --concurrency=200 -P eventlet -Q celery,processing,video,upload,notification

pause
