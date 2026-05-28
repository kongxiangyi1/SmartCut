@echo off
REM 快速禁用 FunASR 模型预加载脚本
REM 运行此脚本后，启动时间将从 144秒 降低到 3秒

echo.
echo ================================================
echo   禁用 ASR 模型预加载
echo ================================================
echo.
echo 效果：
echo   - 启动时间: 144秒 → 3秒
echo   - 首次使用: 需要等待模型加载
echo   - 后续使用: 无影响
echo.
echo ================================================
echo.

REM 检查是否已经设置
if defined DISABLE_ASR_PRELOAD (
    if "%DISABLE_ASR_PRELOAD%"=="true" (
        echo [OK] ASR 预加载已被禁用
        echo   当前 DISABLE_ASR_PRELOAD=%DISABLE_ASR_PRELOAD%
        echo.
        echo 如需重新启用，请运行:
        echo   set DISABLE_ASR_PRELOAD=false
        echo.
        pause
        exit /b 0
    )
)

REM 设置环境变量（仅当前窗口生效）
set DISABLE_ASR_PRELOAD=true

echo.
echo [OK] 已设置 DISABLE_ASR_PRELOAD=true
echo.
echo 此设置仅在当前窗口生效。
echo 如需永久生效，请:
echo.
echo 方式1: 将以下行添加到系统环境变量
echo   DISABLE_ASR_PRELOAD=true
echo.
echo 方式2: 在项目根目录创建 .env 文件
echo   echo DISABLE_ASR_PRELOAD=true ^> .env
echo.
echo 方式3: 修改 backend/main.py（推荐永久方案）
echo   在文件开头添加:
echo     import os
echo     os.environ["DISABLE_ASR_PRELOAD"] = "true"
echo.
echo ================================================
echo.

pause
