# AutoClip 发布打包脚本
# 将整个应用打包为可分发的安装包

param(
    [string]$Version = "1.0.0",
    [string]$OutputDir = "$PSScriptRoot\..\releases",
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$IncludeModels,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# 颜色输出函数
function Write-Step { param([string]$Msg) Write-Host "📦 $Msg" -ForegroundColor Cyan }
function Write-Success { param([string]$Msg) Write-Host "✅ $Msg" -ForegroundColor Green }
function Write-Warning { param([string]$Msg) Write-Host "⚠️  $Msg" -ForegroundColor Yellow }
function Write-Error { param([string]$Msg) Write-Host "❌ $Msg" -ForegroundColor Red }

# 获取项目根目录
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$OutputDir = $ExecutionContext.InvokeProvider.Namespaces["Environment"].GetValue("TEMP")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoClip 发布打包工具 v$Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 清理函数
function Clear-PackageDir {
    param([string]$Dir)

    if (Test-Path $Dir) {
        Write-Step "清理旧包: $Dir"
        Remove-Item -Path $Dir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
}

# 获取 Whisper 模型
function Get-WhisperModels {
    $cacheDir = if ($IsWindows) {
        Join-Path $env:LOCALAPPDATA "Cache\whisper"
    } else {
        Join-Path $HOME ".cache/whisper"
    }

    $models = @{
        "tiny" = @{ Size = 72; File = "tiny.pt" }
        "base" = @{ Size = 139; File = "base.pt" }
    }

    Write-Step "检查 Whisper 模型..."

    $foundModels = @()
    foreach ($modelName in $models.Keys) {
        $modelPath = Join-Path $cacheDir $models[$modelName].File
        if (Test-Path $modelPath) {
            $sizeMB = (Get-Item $modelPath).Length / 1MB
            if ($sizeMB -gt 50) {
                Write-Success "找到 $modelName : $sizeMB MB"
                $foundModels += $modelName
            }
        }
    }

    return @{
        CacheDir = $cacheDir
        Models = $foundModels
    }
}

# 复制文件函数
function Copy-Directory {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$Exclude = @()
    )

    if (-not (Test-Path $Source)) {
        Write-Warning "源目录不存在: $Source"
        return
    }

    $items = Get-ChildItem -Path $Source -Recurse
    foreach ($item in $items) {
        $relativePath = $item.FullName.Substring($Source.Length).TrimStart("\")
        $excluded = $false

        foreach ($pattern in $Exclude) {
            if ($relativePath -like $pattern) {
                $excluded = $true
                break
            }
        }

        if (-not $excluded) {
            $destPath = Join-Path $Dest $relativePath
            $destDir = Split-Path $destPath -Parent

            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }

            if (-not $item.PSIsContainer) {
                Copy-Item -Path $item.FullName -Destination $destPath -Force
            }
        }
    }
}

# 打包前端
function Build-Frontend {
    param([string]$OutputPackage)

    Write-Step "构建前端..."

    if ($SkipFrontend) {
        Write-Warning "跳过前端构建"
        return
    }

    $frontendBuildDir = Join-Path $OutputPackage "frontend"
    New-Item -ItemType Directory -Path $frontendBuildDir -Force | Out-Null

    Push-Location $FrontendDir
    try {
        # 安装依赖
        Write-Host "   安装前端依赖..." -ForegroundColor Gray
        npm install 2>&1 | Out-Null

        # 构建
        Write-Host "   执行构建..." -ForegroundColor Gray
        npm run build 2>&1 | Out-Null

        if (Test-Path "dist") {
            Copy-Item -Path "dist\*" -Destination $frontendBuildDir -Recurse -Force
            Write-Success "前端构建完成"
        } else {
            Write-Error "前端构建失败"
        }
    } finally {
        Pop-Location
    }
}

# 打包后端
function Build-Backend {
    param(
        [string]$OutputPackage,
        [hashtable]$WhisperInfo
    )

    Write-Step "打包后端..."

    if ($SkipBackend) {
        Write-Warning "跳过后端打包"
        return
    }

    $backendPackageDir = Join-Path $OutputPackage "backend"
    New-Item -ItemType Directory -Path $backendPackageDir -Force | Out-Null

    # 复制后端代码
    Write-Host "   复制后端代码..." -ForegroundColor Gray
    $excludePatterns = @(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "tests",
        "*.egg-info"
    )
    Copy-Directory -Source $BackendDir -Dest $backendPackageDir -Exclude $excludePatterns

    # 复制 Whisper 模型
    if ($IncludeModels -and $WhisperInfo.Models.Count -gt 0) {
        Write-Step "复制 Whisper 模型..."
        $modelsDestDir = Join-Path $backendPackageDir "models\whisper"
        New-Item -ItemType Directory -Path $modelsDestDir -Force | Out-Null

        foreach ($modelName in $WhisperInfo.Models) {
            $src = Join-Path $WhisperInfo.CacheDir "$modelName.pt"
            $dst = Join-Path $modelsDestDir "$modelName.pt"
            Copy-Item -Path $src -Destination $dst -Force
            $sizeMB = (Get-Item $src).Length / 1MB
            Write-Success "已复制模型: $modelName ($sizeMB MB)"
        }
    }

    Write-Success "后端打包完成"
}

# 生成启动脚本
function New-StartupScripts {
    param([string]$OutputPackage)

    Write-Step "生成启动脚本..."

    # Windows 启动脚本
    $startScript = @"
@echo off
chcp 65001 > nul
title AutoClip

echo ========================================
echo   AutoClip 启动中...
echo ========================================

REM 启动后端服务
echo [1/2] 启动后端服务...
cd /d "%~dp0backend"
start "AutoClip-Backend" cmd /k python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

REM 等待后端启动
timeout /t 3 /nobreak > nul

REM 启动前端服务
echo [2/2] 启动前端服务...
cd /d "%~dp0frontend"
start "AutoClip-Frontend" cmd /k npm run dev

echo.
echo ========================================
echo   AutoClip 启动完成！
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000
echo ========================================
echo.
echo 按任意键打开浏览器...
pause > nul
start http://localhost:3000
"@

    $startScriptPath = Join-Path $OutputPackage "启动 AutoClip.bat"
    Set-Content -Path $startScriptPath -Value $startScript -Encoding UTF8

    # PowerShell 启动脚本
    $psScript = @"
# AutoClip 启动脚本
`$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoClip 启动中..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

`$BackendDir = Split-Path `$PSScriptRoot -Parent
`$BackendPort = 8000
`$FrontendPort = 3000

# 启动后端
Write-Host "[1/2] 启动后端服务 (端口 `$BackendPort)..." -ForegroundColor Yellow
Start-Process -FilePath "python" `
    -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port `$BackendPort" `
    -WorkingDirectory (Join-Path `$BackendDir "backend") `
    -WindowStyle Normal

Start-Sleep -Seconds 3

# 启动前端
Write-Host "[2/2] 启动前端服务 (端口 `$FrontendPort)..." -ForegroundColor Yellow
Start-Process -FilePath "npm" `
    -ArgumentList "run dev" `
    -WorkingDirectory (Join-Path `$BackendDir "frontend") `
    -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  AutoClip 启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "前端: http://localhost:`$FrontendPort" -ForegroundColor White
Write-Host "后端: http://localhost:`$BackendPort" -ForegroundColor White
Write-Host ""

# 自动打开浏览器
Start-Process "http://localhost:`$FrontendPort"
"@

    $psScriptPath = Join-Path $OutputPackage "启动 AutoClip.ps1"
    Set-Content -Path $psScriptPath -Value $psScript -Encoding UTF8

    Write-Success "启动脚本已生成"
}

# 生成配置说明
function New-Readme {
    param(
        [string]$OutputPackage,
        [hashtable]$WhisperInfo
    )

    $readmeContent = @"
# AutoClip 安装包

## 版本
$Version

## 包含内容

### 1. 前端 (React + Vite)
- 位置: `frontend/`
- 端口: 3000
- 技术栈: React 18, Ant Design 5, TypeScript

### 2. 后端 (FastAPI + SQLAlchemy)
- 位置: `backend/`
- 端口: 8000
- 技术栈: Python 3.9+, FastAPI, Redis

### 3. Whisper 离线模型
$(
    if ($WhisperInfo.Models.Count -gt 0) {
        foreach ($model in $WhisperInfo.Models) {
            "   - $model"
        }
    } else {
        "   - 未包含（首次使用会自动下载）"
    }
)

## 系统要求

- 操作系统: Windows 10+ / macOS 10.14+ / Ubuntu 18.04+
- 内存: 最少 4GB RAM（推荐 8GB+）
- 磁盘空间: 最少 2GB 可用空间
- Python: 3.9 或更高版本
- Node.js: 18 或更高版本

## 安装步骤

### Windows
1. 解压本压缩包到任意目录
2. 双击运行 `启动 AutoClip.bat`
3. 等待服务启动完成，浏览器将自动打开

### macOS / Linux
1. 解压本压缩包到任意目录
2. 打开终端，进入解压目录
3. 运行: `chmod +x 启动 AutoClip.ps1 && pwsh 启动 AutoClip.ps1`

## 离线使用

$(
    if ($WhisperInfo.Models.Count -gt 0) {
        "本安装包已包含 Whisper 离线模型，可以完全离线使用。"
    } else {
        "本安装包未包含 Whisper 模型，首次使用需要联网下载。"
    }
)

如需添加离线模型:
1. 从已安装 Whisper 的机器复制 `~/.cache/whisper/` 目录
2. 将模型文件复制到 `backend/models/whisper/` 目录

## 语音识别优先级

1. 云端 API (OpenAI/Azure/Google) - 最精准，需要网络
2. 本地 Whisper 模型 - 已打包，无需网络
3. 能量 VAD 兜底 - 完全离线，只有时间戳

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3000 | Web 界面 |
| 后端 | 8000 | API 服务 |
| Redis | 6379 | 进度消息 |

## 故障排除

### 端口被占用
如果端口 3000 或 8000 被占用，修改以下文件:
- `backend/main.py` - 修改 uvicorn 端口
- `frontend/vite.config.ts` - 修改代理配置

### 模型加载失败
检查 `backend/models/whisper/` 目录是否存在 .pt 文件

### 前端无法连接后端
检查后端是否正常运行: http://localhost:8000/docs

## 技术支持

如遇问题，请提交 Issue 到 GitHub 仓库。
"@

    $readmePath = Join-Path $OutputPackage "README.txt"
    Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8
}

# 生成离线模型配置
function New-ModelConfig {
    param([string]$OutputPackage)

    $configContent = @"
# AutoClip 离线模型配置
# 此文件由打包脚本自动生成

# Whisper 模型目录
WHISPER_MODELS_PATH=..\..\offline_packages\whisper_models
"@

    $configDir = Join-Path $OutputPackage "config"
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null

    $configPath = Join-Path $configDir "offline_models.env"
    Set-Content -Path $configPath -Value $configContent -Encoding UTF8
}

# 主执行流程
try {
    # 检查 Python
    Write-Step "检查环境..."
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python 未安装或不在 PATH 中"
    }
    Write-Success "Python: $pythonVersion"

    # 检查 Node.js
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Node.js 未安装或不在 PATH 中"
    }
    Write-Success "Node.js: $nodeVersion"

    # 创建输出目录
    $packageDir = Join-Path $OutputDir "AutoClip-$Version"
    if ($Clean) {
        Clear-PackageDir -Dir $packageDir
    }

    # 获取 Whisper 模型信息
    $whisperInfo = Get-WhisperModels

    # 打包
    Build-Frontend -OutputPackage $packageDir
    Build-Backend -OutputPackage $packageDir -WhisperInfo $whisperInfo

    # 生成脚本和文档
    New-StartupScripts -OutputPackage $packageDir
    New-Readme -OutputPackage $packageDir -WhisperInfo $whisperInfo
    New-ModelConfig -OutputPackage $packageDir

    # 计算包大小
    $totalSize = (Get-ChildItem -Path $packageDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  打包完成！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 包位置: $packageDir" -ForegroundColor White
    Write-Host "📊 包大小: $totalSize GB" -ForegroundColor White
    Write-Host ""
    Write-Host "包含模型: $($whisperInfo.Models -join ', ')" -ForegroundColor Cyan

    # 创建 ZIP 压缩包
    Write-Step "创建压缩包..."
    $zipPath = Join-Path $OutputDir "AutoClip-$Version.zip"

    Compress-Archive -Path "$packageDir\*" -DestinationPath $zipPath -Force
    $zipSize = (Get-Item $zipPath).Length / 1GB

    Write-Success "压缩包已创建: $zipPath ($zipSize GB)"

} catch {
    Write-Error "打包失败: $_"
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    exit 1
}
