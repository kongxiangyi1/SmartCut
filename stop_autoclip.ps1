#!/usr/bin/env pwsh

# AutoClip 停止脚本
# 功能: 停止所有相关服务

$GREEN = "`e[0;32m"
$BLUE = "`e[0;34m"
$YELLOW = "`e[1;33m"
$RED = "`e[0;31m"
$NC = "`e[0m"

$PROJECT_ROOT = $PSScriptRoot
$BACKEND_PID_FILE = Join-Path $PROJECT_ROOT "backend.pid"
$FRONTEND_PID_FILE = Join-Path $PROJECT_ROOT "frontend.pid"
$CELERY_PID_FILE = Join-Path $PROJECT_ROOT "celery.pid"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "INFO" { $BLUE }
        "SUCCESS" { $GREEN }
        "WARNING" { $YELLOW }
        "ERROR" { $RED }
        default { $NC }
    }
    Write-Host "${color}[$timestamp] [$Level] $Message${NC}"
}

function Stop-ProcessByFile {
    param([string]$PidFile, [string]$ServiceName)

    if (Test-Path $PidFile) {
        $content = Get-Content $PidFile -Raw -ErrorAction SilentlyContinue
        if ($content -match '^\s*(\d+)\s*$') {
            $processId = [int]$matches[1]
            Write-Log "Stopping $ServiceName (PID: $processId)..." "INFO"
            try {
                $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if ($process) {
                    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Milliseconds 500
                    $stillRunning = Get-Process -Id $processId -ErrorAction SilentlyContinue
                    if ($stillRunning) {
                        Write-Log "$ServiceName timeout, forcing termination..." "WARNING"
                        Stop-Process -Id $processId -Force -Confirm:$false -ErrorAction SilentlyContinue
                    }
                }
                Write-Log "$ServiceName stopped" "SUCCESS"
            }
            catch {
                $errMsg = $_.Exception.Message
                Write-Log "Error stopping ${ServiceName}: $errMsg" "WARNING"
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "${YELLOW}===============================================${NC}"
Write-Host "${YELLOW}        AutoClip Service Stop Script            ${NC}"
Write-Host "${YELLOW}===============================================${NC}"
Write-Host ""

Write-Log "Stopping all AutoClip services..." "INFO"
Write-Host ""

Stop-ProcessByFile -PidFile $CELERY_PID_FILE -ServiceName "Celery Worker"
Stop-ProcessByFile -PidFile $FRONTEND_PID_FILE -ServiceName "Frontend"
Stop-ProcessByFile -PidFile $BACKEND_PID_FILE -ServiceName "Backend"

$remainingPorts = @(8001, 3000)
foreach ($port in $remainingPorts) {
    $proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    if ($proc) {
        foreach ($processId in $proc) {
            $processName = (Get-Process -Id $processId -ErrorAction SilentlyContinue).ProcessName
            Write-Log "Found process using port ${port} (PID: $processId, Name: $processName), stopping..." "WARNING"
            Stop-Process -Id $processId -Force -Confirm:$false -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
Write-Log "All services stopped" "SUCCESS"
Write-Host ""

Write-Host "${GREEN}===============================================${NC}"
Write-Host ""