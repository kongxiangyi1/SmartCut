@echo off
chcp 65001 >nul
echo ========================================
echo   AutoClip 服务启动器 (Windows版)
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] 检查虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在
    echo 请先运行: python -m venv venv
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo.
echo [2/5] 启动 Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo 启动 Redis 服务...
    redis-server --daemonize yes
    timeout /t 2 /nobreak >nul
) else (
    echo Redis 已运行
)

echo.
echo [3/5] 启动 Celery Worker (Eventlet模式 - 支持多核)...
start "Celery Worker" cmd /k "python -m celery -A backend.core.celery_app worker --loglevel=info --concurrency=200 -P eventlet -Q celery,processing,video,upload,notification"

echo.
echo [4/5] 启动后端 API 服务...
start "Backend API" cmd /k "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [5/5] 启动前端开发服务器（热重载）...
cd frontend
start "Frontend Dev" cmd /k "npm run dev"
cd /d "%~dp0"

echo.
echo ========================================
echo   所有服务已启动!
echo ========================================
echo.
echo 服务地址:
echo   - 后端API:     http://localhost:8000
echo   - 前端页面:    http://localhost:3000  （热重载，改代码即时生效）
echo   - API文档:     http://localhost:8000/docs
echo.
echo 热部署说明:
echo   - 改后端 .py 文件 → 自动重启（~2秒）
echo   - 改前端 .tsx 文件 → 浏览器即时更新（无需刷新）
echo.
echo 关闭窗口不会停止服务
echo 按任意键退出此窗口...
pause >nul
