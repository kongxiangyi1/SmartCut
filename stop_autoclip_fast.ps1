#!/usr/bin/env pwsh

# AutoClip 停止脚本 - 极速版
# 功能: 快速停止所有相关服务
# 特点: 去掉所有可能卡住的操作

$PROJECT_ROOT = $PSScriptRoot

Write-Host ""
Write-Host "==============================================="
Write-Host "       AutoClip Stop Script (Fast Mode)       "
Write-Host "==============================================="
Write-Host ""

Write-Host "[1/4] Cleaning PID files..." -ForegroundColor Cyan
Get-ChildItem -Path $PROJECT_ROOT -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  Removing $($_.Name)"
    Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "[2/4] Stopping processes on known ports..." -ForegroundColor Cyan
$ports = @(8090, 3000, 5555)
$stoppedCount = 0

foreach ($port in $ports) {
    try {
        # 使用 netstat + taskkill，这是最快的方式
        $output = netstat -ano | Select-String ":$port\s"
        if ($output) {
            $pids = $output | ForEach-Object {
                if ($_ -match '(\d+)\s*$') { $matches[1] }
            } | Select-Object -Unique

            foreach ($pid in $pids) {
                if ($pid -and $pid -gt 0) {
                    try {
                        # 先获取进程名
                        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                        $name = if ($proc) { $proc.ProcessName } else { "unknown" }
                        Write-Host "  Killing PID $pid ($name) on port $port" -ForegroundColor Yellow

                        # 快速终止
                        taskkill /F /PID $pid | Out-Null
                        $stoppedCount++
                    } catch {}
                }
            }
        }
    } catch {}
}

Write-Host ""
Write-Host "[3/4] Cleaning related processes..." -ForegroundColor Cyan

# 快速查找并终止相关进程
try {
    $targetPatterns = @(
        "python.*autoclip",
        "uvicorn.*autoclip",
        "node.*vite",
        "node.*react-scripts"
    )

    # 先获取所有 Python 和 Node 进程
    $candidates = Get-Process -ErrorAction SilentlyContinue |
                  Where-Object { $_.ProcessName -match "python|node" }

    foreach ($proc in $candidates) {
        # 检查是否是我们需要停止的
        $cmdLine = ""
        try {
            # 使用 WMI 获取命令行（更可靠）
            $wmiProc = Get-WmiObject Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
            if ($wmiProc) {
                $cmdLine = $wmiProc.CommandLine
            }
        } catch {}

        # 检查路径或命令行是否包含项目目录
        $isTarget = $false
        try {
            if ($proc.Path -and $proc.Path -match [regex]::Escape($PROJECT_ROOT)) {
                $isTarget = $true
            }
        } catch {}

        if (-not $isTarget -and $cmdLine) {
            if ($cmdLine -match [regex]::Escape($PROJECT_ROOT)) {
                $isTarget = $true
            }
            foreach ($pat in $targetPatterns) {
                if ($cmdLine -match $pat) {
                    $isTarget = $true
                    break
                }
            }
        }

        if ($isTarget) {
            Write-Host "  Killing $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
            try {
                taskkill /F /PID $proc.Id | Out-Null
                $stoppedCount++
            } catch {}
        }
    }
} catch {}

Write-Host ""
Write-Host "[4/4] Verifying and finishing..." -ForegroundColor Cyan

# 等待一会儿
Start-Sleep -Seconds 2

# 验证端口
$allPortsFree = $true
foreach ($port in $ports) {
    try {
        $check = netstat -ano | Select-String ":$port\s"
        if ($check) {
            Write-Host "  WARNING: Port $port is still in use!" -ForegroundColor Red
            $allPortsFree = $false
        }
    } catch {}
}

Write-Host ""
if ($allPortsFree) {
    Write-Host "✅ All services stopped successfully!" -ForegroundColor Green
    Write-Host "   Total processes killed: $stoppedCount"
} else {
    Write-Host "⚠️ Stop completed but some ports are still in use." -ForegroundColor Yellow
    Write-Host "   You may need to kill remaining processes manually."
}

Write-Host ""
Write-Host "==============================================="
Write-Host ""
