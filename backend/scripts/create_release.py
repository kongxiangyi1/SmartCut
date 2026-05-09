import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

project_root = Path('d:/Download/autoclip-main1/autoclip-main')
release_dir = project_root / 'releases'
release_dir.mkdir(exist_ok=True)

version = '1.0.0'
package_name = f'AutoClip-{version}'
package_dir = release_dir / package_name

print(f'创建发布包: {package_name}')

if package_dir.exists():
    print('  [注意] 目录已存在，正在删除旧文件...')
    import time
    for retry in range(3):
        try:
            shutil.rmtree(package_dir)
            break
        except PermissionError:
            if retry < 2:
                time.sleep(1)
            else:
                print('  [警告] 无法删除目录，将尝试清理内部文件...')

package_dir.mkdir(parents=True, exist_ok=True)

exclude_patterns = ['__pycache__', '.git', '.venv', 'venv', 'node_modules', 'tests', '*.pyc', '*.pyo', '*.rdb', '*.pid', 'data']

def should_copy(path_str):
    for pattern in exclude_patterns:
        if pattern in path_str:
            return False
    return True

print('复制后端代码...')
backend_src = project_root / 'backend'
backend_dest = package_dir / 'backend'

for item in backend_src.rglob('*'):
    if item.is_file() and should_copy(str(item)):
        rel_path = item.relative_to(backend_src)
        dest_file = backend_dest / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest_file)

# 复制 requirements.txt（从项目根目录）
requirements_src = project_root / 'requirements.txt'
if requirements_src.exists():
    shutil.copy2(requirements_src, backend_dest / 'requirements.txt')
    print('  requirements.txt 已复制')
else:
    print('  [警告] 未找到 requirements.txt')

print('  后端代码已复制')

print('复制离线模型...')
models_src = project_root / 'offline_packages' / 'whisper_models'
models_dest = package_dir / 'offline_packages' / 'whisper_models'
models_dest.mkdir(parents=True, exist_ok=True)

if models_src.exists():
    for model_file in models_src.glob('*.pt'):
        shutil.copy2(model_file, models_dest / model_file.name)
        size_mb = model_file.stat().st_size / (1024 * 1024)
        print(f'  {model_file.name} ({size_mb:.1f} MB)')
else:
    print('  未找到离线模型目录')

print('复制前端构建产物...')
frontend_dist = project_root / 'frontend' / 'dist'
frontend_dest = package_dir / 'frontend' / 'dist'

if frontend_dist.exists():
    shutil.copytree(frontend_dist, frontend_dest, dirs_exist_ok=True)
    print('  前端构建产物已复制')
else:
    print('  未找到前端构建目录，复制源码...')
    frontend_src = project_root / 'frontend'
    shutil.copytree(frontend_src / 'src', package_dir / 'frontend' / 'src', dirs_exist_ok=True)
    shutil.copytree(frontend_src / 'public', package_dir / 'frontend' / 'public', dirs_exist_ok=True)
    for f in ['package.json', 'vite.config.ts', 'tsconfig.json', 'index.html']:
        src_f = frontend_src / f
        if src_f.exists():
            shutil.copy2(src_f, package_dir / 'frontend' / f)
    print('  前端源码已复制')

print('创建启动脚本...')
start_script = '''@echo off
chcp 65001 > nul
title AutoClip

echo ========================================
echo   AutoClip 启动中...
echo ========================================

echo [1/1] 启动 AutoClip 服务...
cd /d "%~dp0backend"
start "AutoClip-Server" cmd /k python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

timeout /t 5 /nobreak > nul

echo.
echo ========================================
echo   AutoClip 启动完成！
echo   访问地址: http://localhost:8000
echo ========================================
echo.
pause > nul
start http://localhost:8000
'''

with open(package_dir / '启动 AutoClip.bat', 'w', encoding='utf-8') as f:
    f.write(start_script)
print('  启动脚本已创建')

print('创建一键安装脚本...')
install_script_path = project_root / 'releases' / package_name / '安装并启动 AutoClip.bat'
if install_script_path.exists():
    with open(install_script_path, 'r', encoding='utf-8') as f:
        install_script = f.read()
else:
    install_script = r'''@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title AutoClip 安装程序
:: [Install script content - fallback if file not found]
'''
    print('  [警告] 安装脚本文件未找到，使用默认内容')

with open(package_dir / '安装并启动 AutoClip.bat', 'w', encoding='utf-8') as f:
    f.write(install_script)
print('  一键安装脚本已创建')

print('创建卸载脚本...')
uninstall_script = r'''@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title AutoClip 卸载程序

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "VENV_DIR=%BACKEND_DIR%\venv"
set "FFMPEG_DIR=%SCRIPT_DIR%ffmpeg"
set "TEMP_PYTHON=%TEMP%\python_installer.exe"
set "TEMP_FFMPEG=%TEMP%\ffmpeg.zip"

echo ========================================
echo      AutoClip 卸载程序
echo ========================================
echo.
echo 此程序将卸载 AutoClip 安装的所有组件：
echo   - Python 虚拟环境 (venv)
echo   - FFmpeg (如果由本安装包安装)
echo   - 临时下载文件
echo.
echo 不会卸载：
echo   - 系统全局安装的 Python
echo   - 其他软件安装的依赖
echo   - 其他软件安装的 FFmpeg
echo.

set /p "CONFIRM=确认卸载 AutoClip? (输入 Y 确认，其他键取消): "
if /i not "!CONFIRM!"=="Y" (
    echo 取消卸载。
    pause
    exit /b 0
)

echo.
echo ========================================
echo 步骤 1/4: 停止运行的服务
echo ========================================

tasklist /FI "WINDOWTITLE eq AutoClip-Server" 2>nul | findstr /i "python.exe" >nul
if %errorLevel% == 0 (
    echo [--] 正在停止 AutoClip 服务...
    taskkill /FI "WINDOWTITLE eq AutoClip-Server" /F >nul 2>&1
    echo [OK] 服务已停止
) else (
    echo [OK] 未发现运行中的 AutoClip 服务
)

wmic process where "name='python.exe' and commandline like '%%uvicorn%%'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%AutoClip%%'" call terminate >nul 2>&1

timeout /t 1 /nobreak >nul

echo.
echo ========================================
echo 步骤 2/4: 删除虚拟环境
echo ========================================

if exist "%VENV_DIR%" (
    echo 正在删除虚拟环境...
    powershell -Command "Remove-Item -Path '%VENV_DIR%' -Recurse -Force -ErrorAction Stop"

    if %errorLevel% == 0 (
        echo [OK] 虚拟环境已删除
    ) else (
        echo [!] 删除虚拟环境时出现问题，尝试重试...
        timeout /t 2 /nobreak >nul
        powershell -Command "Remove-Item -Path '%VENV_DIR%' -Recurse -Force"
        if exist "%VENV_DIR%" (
            echo [ERR] 无法删除虚拟环境，可能被其他程序占用
            echo 请关闭所有 Python 相关程序后重试
            pause
            exit /b 1
        ) else (
            echo [OK] 虚拟环境已删除
        )
    )
) else (
    echo [OK] 未找到虚拟环境
)

echo.
echo ========================================
echo 步骤 3/4: 删除 FFmpeg (如果由本安装包安装)
echo ========================================

if exist "%FFMPEG_DIR%" (
    echo 正在删除 FFmpeg...
    if exist "%FFMPEG_DIR%\ffmpeg.exe" (
        powershell -Command "Remove-Item -Path '%FFMPEG_DIR%' -Recurse -Force"

        if %errorLevel% == 0 (
            echo [OK] FFmpeg 已删除
        ) else (
            echo [!] 删除 FFmpeg 时出现问题，尝试重试...
            timeout /t 2 /nobreak >nul
            powershell -Command "Remove-Item -Path '%FFMPEG_DIR%' -Recurse -Force"
            if exist "%FFMPEG_DIR%" (
                echo [ERR] 无法删除 FFmpeg，可能被其他程序占用
                echo 请关闭所有使用 FFmpeg 的程序后重试
            ) else (
                echo [OK] FFmpeg 已删除
            )
        )
    ) else (
        echo [OK] FFmpeg 目录不是由本安装包创建，跳过
    )
) else (
    echo [OK] 未找到 FFmpeg
)

echo.
echo ========================================
echo 步骤 4/4: 清理临时文件
echo ========================================

if exist "%TEMP_PYTHON%" (
    del /f /q "%TEMP_PYTHON%" >nul 2>&1
    echo [OK] Python 安装器临时文件已清理
)

if exist "%TEMP_FFMPEG%" (
    del /f /q "%TEMP_FFMPEG%" >nul 2>&1
    echo [OK] FFmpeg 压缩包临时文件已清理
)

set "PIP_CACHE=%USERPROFILE%\AppData\Local\pip\cache"
if exist "%PIP_CACHE%" (
    echo [--] 是否清理 pip 缓存? (可释放约 100-500 MB 空间)
    set /p "CLEAN_CACHE=输入 Y 清理，其他键跳过: "
    if /i "!CLEAN_CACHE!"=="Y" (
        rd /s /q "%PIP_CACHE%" >nul 2>&1
        echo [OK] pip 缓存已清理
    ) else (
        echo [OK] pip 缓存未清理
    )
)

echo.
echo ========================================
echo      卸载完成！
echo ========================================
echo.
echo 已删除：
echo   - Python 虚拟环境
echo   - FFmpeg (如果由本安装包安装)
echo   - 临时下载文件
echo.
echo 如需重新安装，请运行: 安装并启动 AutoClip.bat
echo.
pause
'''

with open(package_dir / '卸载 AutoClip.bat', 'w', encoding='utf-8') as f:
    f.write(uninstall_script)
print('  卸载脚本已创建')

readme_content = f'''AutoClip 安装包 v{version}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

== 包含内容 ==

后端
- FastAPI 后端服务
- Whisper 离线模型: tiny + base (约210 MB)

前端
- React + TypeScript 预构建产物
- 无需额外构建即可运行

== 安装步骤 ==

方式一：一键安装
  双击运行 安装并启动 AutoClip.bat
  (会自动安装 Python、FFmpeg 和所有依赖)

方式二：手动安装
  1. 安装 Python 3.9+
  2. 安装 FFmpeg (添加到系统 PATH)
  3. cd backend
  4. python -m venv venv
  5. venv\\Scripts\\pip.exe install -r requirements.txt

== 启动方式 ==

Windows: 双击运行 启动 AutoClip.bat

或手动启动:
cd backend
venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

访问地址: http://localhost:8000

== 卸载方式 ==

双击运行 卸载 AutoClip.bat

卸载内容：
  - Python 虚拟环境 (venv)
  - FFmpeg (由本安装包安装的)
  - 临时下载文件

不会卸载：
  - 系统全局安装的 Python
  - 其他软件安装的依赖
  - 其他软件安装的 FFmpeg

== 离线功能 ==

已包含 Whisper tiny + base 模型
完全离线可用语音识别
无需联网即可使用核心功能

== 镜像源 ==

依赖安装默认使用清华镜像源
如果镜像源不可用，会自动回退到官方源

== 技术支持 ==

如遇问题，请检查日志或提交 Issue。
'''

with open(package_dir / 'README.txt', 'w', encoding='utf-8') as f:
    f.write(readme_content)
print('  README 已创建')

total_size = sum(f.stat().st_size for f in package_dir.rglob('*') if f.is_file())
print(f'\\n包大小: {total_size / (1024*1024*1024):.2f} GB')

print('\\n创建压缩包...')
zip_path = release_dir / f'{package_name}.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for file in package_dir.rglob('*'):
        if file.is_file():
            arcname = file.relative_to(package_dir)
            zipf.write(file, arcname)

zip_size = zip_path.stat().st_size / (1024*1024*1024)
print(f'  {zip_path.name} ({zip_size:.2f} GB)')

print('\\n========================================')
print('  发布包创建完成！')
print('========================================')
print(f'\\n位置: {zip_path}')
print(f'大小: {zip_size:.2f} GB')