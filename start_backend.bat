@echo off
setlocal

:: 设置项目根目录
set "PROJECT_ROOT=E:\ClipProject\autoclip-main1\autoclip-main"

:: 设置虚拟环境 Python 路径
set "PYTHON_EXE=%PROJECT_ROOT%\venv\Scripts\python.exe"

:: 设置 PYTHONPATH
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend"

:: 启动后端服务
echo Starting backend server...
cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8003

endlocal