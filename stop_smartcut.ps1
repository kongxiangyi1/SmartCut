#!/usr/bin/env pwsh

$PROJECT_ROOT = $PSScriptRoot
$BACKEND_PID_FILE = Join-Path $PROJECT_ROOT "backend.pid"
$FRONTEND_PID_FILE = Join-Path $PROJECT_ROOT "frontend.pid"
$CELERY_PID_FILE = Join-Path $PROJECT_ROOT "celery.pid"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = switch ($Level) {
        "INFO" { "[INFO]" }
        "SUCCESS" { "[OK]" }
        "WARNING" { "[WARN]" }
        "ERROR" { "[ERROR]" }
        default { "" }
    }
    Write-Host "$timestamp $prefix $Message"
}

function Test-ProcessExists {
    param([int]$ProcessId)
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    return ($null -ne $process)
}

function Stop-ProcessSafely {
    param([int]$ProcessId, [string]$ServiceName, [int]$TimeoutSeconds = 10)
    if (-not (Test-ProcessExists -ProcessId $ProcessId)) {
        Write-Log "$ServiceName (PID: $ProcessId) not found, may have already stopped" "INFO"
        return $true
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $processName = if ($process) { $process.ProcessName } else { "Unknown" }
    Write-Log "Stopping $ServiceName (PID: $ProcessId, Name: $processName)..." "INFO"
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        $elapsed = 0
        while ($elapsed -lt $TimeoutSeconds) {
            Start-Sleep -Milliseconds 500
            $elapsed += 0.5
            if (-not (Test-ProcessExists -ProcessId $ProcessId)) {
                Write-Log "$ServiceName stopped successfully" "SUCCESS"
                return $true
            }
        }
        Write-Log "$ServiceName timeout, forcing termination..." "WARNING"
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-Process -Id $child.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        if (Test-ProcessExists -ProcessId $ProcessId) {
            Write-Log "Failed to stop $ServiceName (PID: $ProcessId)" "ERROR"
            return $false
        }
        Write-Log "$ServiceName stopped" "SUCCESS"
        return $true
    } catch {
        Write-Log "Error stopping ${ServiceName}: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Stop-ProcessByFile {
    param([string]$PidFile, [string]$ServiceName)
    if (-not (Test-Path $PidFile)) {
        Write-Log "$ServiceName PID file not found, skipping..." "INFO"
        return
    }
    try {
        $content = Get-Content $PidFile -Raw -ErrorAction Stop
        if ($content -match '(\d+)') {
            $processId = [int]$matches[1]
            $result = Stop-ProcessSafely -ProcessId $processId -ServiceName $ServiceName
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        } else {
            Write-Log "$ServiceName PID file has invalid format, removing..." "WARNING"
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Log "Error reading PID file ${PidFile}: $($_.Exception.Message)" "WARNING"
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ProcessesOnPort {
    param([int]$Port)
    try {
        $foundPids = netstat -ano | Select-String ":$Port\s" | ForEach-Object {
            if ($_ -match '\s+(\d+)\s*$') { [int]$matches[1] }
        } | Where-Object { $_ -gt 0 } | Select-Object -Unique
        foreach ($processId in $foundPids) {
            Stop-ProcessSafely -ProcessId $processId -ServiceName "Port $Port listener"
        }
    } catch {
        Write-Log "Error checking port $Port : $($_.Exception.Message)" "WARNING"
    }
}

function Stop-ProjectProcesses {
    Write-Log "Searching for AutoClip-related processes..." "INFO"
    $serviceNames = @("uvicorn", "celery", "vite", "react-scripts")
    $currentPid = $PID
    $editorNames = "code|trae|cursor|explorer|vim|nano|sublime|atom|electron"
    $allProcesses = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Id -ne $currentPid -and (
                $_.ProcessName -match "python|node|python3" -or
                $_.MainWindowTitle -match "autoclip|auto.?clip"
            )
        }
    foreach ($proc in $allProcesses) {
        $shouldStop = $false
        if ($proc.ProcessName -match $editorNames) {
            continue
        }
        if ($proc.MainWindowTitle -match "smartcut|smart.?cut") {
            $shouldStop = $true
        }
        foreach ($svcName in $serviceNames) {
            if ($proc.ProcessName -match $svcName) {
                $shouldStop = $true
                break
            }
        }
        if ($shouldStop) {
            Write-Log "Found SmartCut process: $($proc.ProcessName) (PID: $($proc.Id))" "WARNING"
            Stop-ProcessSafely -ProcessId $proc.Id -ServiceName "SmartCut process"
        }
    }
}

function Test-PortAvailable {
    param([int]$Port)
    try {
        $stillInUse = netstat -ano | Select-String ":$Port\s"
        return ($null -eq $stillInUse -or $stillInUse.Count -eq 0)
    } catch {
        return $true
    }
}

Write-Host ""
Write-Host "==============================================="
Write-Host "     SmartCut Service Stop Script              "
Write-Host "==============================================="
Write-Host ""

Write-Log "Starting service stop procedure..." "INFO"
Write-Host ""

Write-Log "Step 1: Stopping registered services..." "INFO"
Stop-ProcessByFile -PidFile $CELERY_PID_FILE -ServiceName "Celery Worker"
Stop-ProcessByFile -PidFile $FRONTEND_PID_FILE -ServiceName "Frontend"
Stop-ProcessByFile -PidFile $BACKEND_PID_FILE -ServiceName "Backend"
Write-Host ""

Write-Log "Step 2: Stopping processes on known ports..." "INFO"
$portsToCheck = @(8090, 3000, 5555)
foreach ($port in $portsToCheck) {
    Write-Log "Checking port $port..." "INFO"
    Stop-ProcessesOnPort -Port $port
}
Write-Host ""

Write-Log "Step 3: Cleaning up project processes..." "INFO"
Stop-ProjectProcesses
Write-Host ""

Write-Log "Step 4: Verifying cleanup..." "INFO"
Start-Sleep -Seconds 3
$blockedPorts = @()
foreach ($port in $portsToCheck) {
    Start-Sleep -Milliseconds 500
    if (-not (Test-PortAvailable -Port $port)) {
        $blockedPorts += $port
        Write-Log "Port $port is still in use" "WARNING"
    } else {
        Write-Log "Port $port is free" "SUCCESS"
    }
}
Write-Host ""
if ($blockedPorts.Count -eq 0) {
    Write-Log "All services stopped successfully" "SUCCESS"
} else {
    Write-Log "Warning: Some ports are still in use: $($blockedPorts -join ', ')" "WARNING"
    Write-Log "You may need to stop these processes manually" "WARNING"
}
Write-Host ""
Write-Host "==============================================="
Write-Host ""
if ($blockedPorts.Count -eq 0) { exit 0 } else { exit 1 }