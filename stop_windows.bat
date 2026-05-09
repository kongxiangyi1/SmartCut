@echo off
chcp 65001 >nul
echo ========================================
echo   AutoClip 服务停止器 (Windows版)
echo ========================================
echo.

echo 停止 Celery Worker...
taskkill /F /IM "celery.exe" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Celery*" >nul 2>&1
echo Celery Worker 已停止

echo.
echo 停止后端 API 服务...
taskkill /F /IM "uvicorn.exe" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Backend*" >nul 2>&1
echo 后端 API 已停止

echo.
echo 停止 Redis (可选)...
echo 如果需要停止 Redis, 请手动运行: redis-cli shutdown
echo.

echo ========================================
echo   所有服务已停止!
echo ========================================
pause
