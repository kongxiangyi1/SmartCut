@echo off
chcp 65001 >nul
echo ========================================
echo   AutoClip 简化版启动器 (Windows)
echo ========================================
echo.
echo 特性: 无需Redis/Celery，单进程运行
echo        适合桌面应用分发
echo.

cd /d "%~dp0"

echo [1/3] 检查虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在
    echo 请先创建虚拟环境: python -m venv venv
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo.
echo [2/3] 设置环境变量...
set USE_SIMPLE_TASK_RUNNER=true

echo.
echo [3/3] 启动后端 API 服务...
echo.
echo 启动中，请稍候...
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
