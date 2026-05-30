@echo off
chcp 65001 >nul
title AutoClip 后端调试

cd /d "%~dp0"

echo ========================================
echo    AutoClip 后端调试启动
echo ========================================
echo.

echo [测试1] 激活虚拟环境...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [失败] 虚拟环境激活失败
    pause
    exit /b 1
)
echo [成功]

echo.
echo [测试2] 检查 Python 版本...
python --version
echo.

echo [测试3] 检查 uvicorn 是否安装...
python -m pip show uvicorn
echo.

echo [测试4] 尝试启动后端...
echo.
echo 即将启动后端，如果这里有错误请截图发给我
echo ========================================
echo.

python backend/main.py --port 8090

echo.
echo 后端已退出，按任意键关闭...
pause
