# AutoClip 离线模型安装脚本
# 将 Whisper tiny + base 模型打包到安装包中

param(
    [string]$ModelsDir = "$PSScriptRoot\..\models\whisper",
    [string]$PackageDir = "$PSScriptRoot\..\offline_packages",
    [switch]$DownloadOnly,
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoClip 离线模型安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Get-WhisperCacheDir {
    if ($IsWindows) {
        return Join-Path $env:LOCALAPPDATA "Cache\whisper"
    } else {
        return Join-Path $HOME ".cache\whisper"
    }
}

function Test-ModelFile {
    param([string]$Path, [int]$ExpectedSizeMB)

    if (-not (Test-Path $Path)) {
        return $false
    }

    $sizeMB = (Get-Item $Path).Length / 1MB
    return $sizeMB -gt ($ExpectedSizeMB * 0.8)
}

function Install-WhisperModels {
    Write-Host "📦 准备安装 Whisper 模型..." -ForegroundColor Yellow
    Write-Host ""

    $cacheDir = Get-WhisperCacheDir
    Write-Host "📂 Whisper 缓存目录: $cacheDir" -ForegroundColor Gray

    if (-not (Test-Path $cacheDir)) {
        New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
    }

    $models = @{
        "tiny" = @{ Size = 72; Description = "最小模型 (72MB) - 速度快，精度一般" }
        "base" = @{ Size = 139; Description = "基础模型 (139MB) - 平衡之选" }
    }

    $downloadedModels = @()

    foreach ($modelName in $models.Keys) {
        $modelPath = Join-Path $cacheDir "$modelName.pt"

        Write-Host "----------------------------------------" -ForegroundColor DarkGray
        Write-Host "🔽 检查模型: $modelName" -ForegroundColor White

        if (Test-ModelFile -Path $modelPath -ExpectedSizeMB $models[$modelName].Size) {
            $sizeMB = (Get-Item $modelPath).Length / 1MB
            Write-Host "   ✅ 模型已存在: $sizeMB MB" -ForegroundColor Green
            $downloadedModels += $modelName
        } else {
            Write-Host "   ⏳ 正在下载 $modelName 模型... ($($models[$modelName].Description))" -ForegroundColor Yellow

            try {
                python -c "import whisper; whisper.load_model('$modelName')" 2>&1 | Out-Null

                if (Test-ModelFile -Path $modelPath -ExpectedSizeMB $models[$modelName].Size) {
                    $sizeMB = (Get-Item $modelPath).Length / 1MB
                    Write-Host "   ✅ 下载完成: $sizeMB MB" -ForegroundColor Green
                    $downloadedModels += $modelName
                } else {
                    Write-Host "   ❌ 下载失败或文件损坏" -ForegroundColor Red
                }
            } catch {
                Write-Host "   ❌ 下载出错: $_" -ForegroundColor Red
            }
        }
    }

    return $downloadedModels
}

function Copy-ModelsToPackage {
    param([string[]]$Models, [string]$SourceDir, [string]$DestDir)

    Write-Host ""
    Write-Host "📦 复制模型到打包目录..." -ForegroundColor Yellow

    $destPath = Join-Path $DestDir "whisper_models"
    if (-not (Test-Path $destPath)) {
        New-Item -ItemType Directory -Path $destPath -Force | Out-Null
    }

    $totalSize = 0

    foreach ($model in $Models) {
        $sourceFile = Join-Path $SourceDir "$model.pt"
        $destFile = Join-Path $destPath "$model.pt"

        if (Test-Path $sourceFile) {
            Copy-Item -Path $sourceFile -Destination $destFile -Force
            $sizeMB = (Get-Item $destFile).Length / 1MB
            $totalSize += $sizeMB
            Write-Host "   ✅ 已复制: $model.pt ($sizeMB MB)" -ForegroundColor Green
        }
    }

    Write-Host ""
    Write-Host "📊 打包统计:" -ForegroundColor Cyan
    Write-Host "   模型总大小: $totalSize MB" -ForegroundColor White
    Write-Host "   打包目录: $destPath" -ForegroundColor White

    return $destPath
}

function Verify-Models {
    param([string]$ModelsDir)

    Write-Host "🔍 验证模型文件..." -ForegroundColor Yellow
    Write-Host ""

    $expectedModels = @{
        "tiny" = 72
        "base" = 139
    }

    $allValid = $true

    foreach ($modelName in $expectedModels.Keys) {
        $modelPath = Join-Path $ModelsDir "$modelName.pt"

        if (Test-Path $modelPath) {
            $sizeMB = (Get-Item $modelPath).Length / 1MB
            $expected = $expectedModels[$modelName]

            if ($sizeMB -gt ($expected * 0.8)) {
                Write-Host "   ✅ $modelName : $sizeMB MB (有效)" -ForegroundColor Green
            } else {
                Write-Host "   ⚠️  $modelName : $sizeMB MB (文件过小)" -ForegroundColor Yellow
                $allValid = $false
            }
        } else {
            Write-Host "   ⭕ $modelName : 未找到" -ForegroundColor Red
            $allValid = $false
        }
    }

    return $allValid
}

function Set-EnvironmentConfig {
    param([string]$ModelsDir)

    Write-Host ""
    Write-Host "⚙️  配置环境变量..." -ForegroundColor Yellow

    $env:WHISPER_MODELS_PATH = $ModelsDir

    $configContent = @"
# Whisper 离线模型配置
WHISPER_MODELS_PATH=$ModelsDir
"@

    $configPath = Join-Path $PSScriptRoot "..\config\offline_models.env"
    $configDir = Split-Path $configPath -Parent

    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    Set-Content -Path $configPath -Value $configContent
    Write-Host "   ✅ 已写入配置: $configPath" -ForegroundColor Green
}

function Show-Summary {
    param(
        [string[]]$DownloadedModels,
        [string]$PackageDir,
        [bool]$AllSuccessful
    )

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  安装完成!" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 已下载的模型:" -ForegroundColor White

    if ($DownloadedModels.Count -gt 0) {
        foreach ($model in $DownloadedModels) {
            Write-Host "   ✅ $model" -ForegroundColor Green
        }
    } else {
        Write-Host "   ❌ 无" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "📊 模型大小:" -ForegroundColor White
    $cacheDir = Get-WhisperCacheDir
    $totalSize = (Get-ChildItem $cacheDir -Filter "*.pt" -ErrorAction SilentlyContinue |
                  Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "   总计: $totalSize MB" -ForegroundColor Cyan

    if ($AllSuccessful) {
        Write-Host ""
        Write-Host "🎉 所有模型安装成功!" -ForegroundColor Green
        Write-Host "   用户现在可以在完全离线的环境下使用 AutoClip" -ForegroundColor Gray
    } else {
        Write-Host ""
        Write-Host "⚠️  部分模型安装失败" -ForegroundColor Yellow
        Write-Host "   请检查网络连接后重试，或手动下载模型" -ForegroundColor Gray
    }

    Write-Host ""
}

function Show-Usage {
    Write-Host @"
用法:
    .\install_offline_models.ps1 [-DownloadOnly] [-VerifyOnly]

参数:
    -DownloadOnly  仅下载模型，不复制到打包目录
    -VerifyOnly    仅验证已安装的模型

示例:
    # 下载并打包模型
    .\install_offline_models.ps1

    # 仅下载模型
    .\install_offline_models.ps1 -DownloadOnly

    # 验证模型
    .\install_offline_models.ps1 -VerifyOnly

"@
}

# 主逻辑
try {
    $cacheDir = Get-WhisperCacheDir

    if ($VerifyOnly) {
        $isValid = Verify-Models -ModelsDir $cacheDir
        exit if ($isValid) { 0 } else { 1 }
    }

    $downloadedModels = Install-WhisperModels

    if ($DownloadOnly) {
        Write-Host ""
        Write-Host "📦 模型已下载到: $cacheDir" -ForegroundColor Cyan
        exit 0
    }

    $packagePath = Copy-ModelsToPackage -Models $downloadedModels -SourceDir $cacheDir -DestDir $PackageDir
    Set-EnvironmentConfig -ModelsDir $cacheDir

    $allSuccessful = $downloadedModels.Count -ge 2
    Show-Summary -DownloadedModels $downloadedModels -PackageDir $packagePath -AllSuccessful $allSuccessful

    exit if ($allSuccessful) { 0 } else { 1 }

} catch {
    Write-Host ""
    Write-Host "❌ 安装失败: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    exit 1
}
