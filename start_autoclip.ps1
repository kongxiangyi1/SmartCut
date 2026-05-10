#!/usr/bin/env pwsh

param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 3000,
    [switch]$SkipStop,
    [switch]$SkipRedis,
    [switch]$Help
)

if ($Help) {
    Write-Host "AutoClip Startup Script"
    Write-Host ""
    Write-Host "Usage: .\start_autoclip.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -BackendPort <port>   Backend port (fixed: 8001)"
    Write-Host "  -FrontendPort <port>  Frontend port (default: 3000)"
    Write-Host "  -SkipStop             Skip stopping old services"
    Write-Host "  -SkipRedis            Skip Redis check"
    Write-Host "  -Help                 Show this help"
    exit 0
}

$ErrorActionPreference = "Continue"

$PROJECT_ROOT = $PSScriptRoot
$LOG_DIR = Join-Path $PROJECT_ROOT "logs"
$BACKEND_PID_FILE = Join-Path $PROJECT_ROOT "backend.pid"
$FRONTEND_PID_FILE = Join-Path $PROJECT_ROOT "frontend.pid"
$CELERY_PID_FILE = Join-Path $PROJECT_ROOT "celery.pid"
$CONFIG_FILE = Join-Path $PROJECT_ROOT "autoclip_ports.json"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "HH:mm:ss"
    $prefix = "[$timestamp] [$Level]"
    switch ($Level) {
        "INFO"    { Write-Host "$prefix $Message" -ForegroundColor Cyan }
        "SUCCESS" { Write-Host "$prefix $Message" -ForegroundColor Green }
        "WARNING" { Write-Host "$prefix $Message" -ForegroundColor Yellow }
        "ERROR"   { Write-Host "$prefix $Message" -ForegroundColor Red }
        default   { Write-Host "$prefix $Message" }
    }
}

function Get-PidFromFile {
    param([string]$PidFile)
    if (Test-Path $PidFile) {
        $content = Get-Content $PidFile -Raw -ErrorAction SilentlyContinue
        if ($content -match '^\s*(\d+)\s*$') {
            return [int]$matches[1]
        }
    }
    return $null
}

function Stop-ProcessByPid {
    param([int]$ProcessId, [string]$ServiceName)
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Log "Stopping $ServiceName (PID: $ProcessId)..." "INFO"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
        if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            Write-Log "$ServiceName stopped" "SUCCESS"
            return $true
        }
        Stop-Process -Id $ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
        Write-Log "$ServiceName forcefully stopped" "WARNING"
        return $true
    }
    return $false
}

function Stop-ServiceByPidFile {
    param([string]$PidFile, [string]$ServiceName)
    $existingPid = Get-PidFromFile -PidFile $PidFile
    if ($existingPid) {
        Stop-ProcessByPid -ProcessId $existingPid -ServiceName $ServiceName
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Kill-ProcessByPort {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Log "Port $Port is used by $($process.ProcessName) (PID: $($process.Id)), terminating..." "WARNING"
                Stop-Process -Id $process.Id -Force -Confirm:$false -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Milliseconds 500
    }
}

function Test-PortAvailable {
    param([int]$Port)
    $connection = New-Object System.Net.Sockets.TcpClient
    try {
        $connection.Connect("127.0.0.1", $Port)
        return $false
    }
    catch {
        return $true
    }
    finally {
        $connection.Dispose()
    }
}

function Get-NextAvailablePort {
    param([int]$StartPort, [int]$MaxTry = 10)
    for ($i = 0; $i -lt $MaxTry; $i++) {
        if (Test-PortAvailable -Port $StartPort) {
            return $StartPort
        }
        $StartPort++
    }
    return $null
}

function Stop-AllServices {
    Write-Log "========== Stopping Old Services ==========" "INFO"

    Stop-ServiceByPidFile -PidFile $CELERY_PID_FILE -ServiceName "Celery Worker"
    Stop-ServiceByPidFile -PidFile $FRONTEND_PID_FILE -ServiceName "Frontend"
    Stop-ServiceByPidFile -PidFile $BACKEND_PID_FILE -ServiceName "Backend"

    $pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*celery*"
    }
    $pythonProcs | ForEach-Object {
        Stop-ProcessByPid -ProcessId $_.Id -ServiceName "Python (uvicorn/celery)"
    }

    Get-Process node -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*vite*"
    } | ForEach-Object {
        Stop-ProcessByPid -ProcessId $_.Id -ServiceName "Node (vite)"
    }

    Start-Sleep -Seconds 1
    Write-Log "Old services stopped" "SUCCESS"
}

function Find-RedisServer {
    $paths = @(
        "C:\Users\KONGXY\scoop\apps\redis\8.6.2\redis-server.exe",
        "C:\Users\KONGXY\scoop\shims\redis-server.exe",
        "$env:LOCALAPPDATA\Microsoft\Redis\redis-server.exe",
        "C:\Program Files\Redis\redis-server.exe",
        "C:\Redis\redis-server.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            return $path
        }
    }
    $which = Get-Command redis-server -ErrorAction SilentlyContinue
    if ($which) {
        return $which.Source
    }
    return $null
}

function Start-RedisService {
    try {
        $redisResult = redis-cli ping 2>&1
        if ($redisResult -eq "PONG") {
            Write-Log "Redis is running" "SUCCESS"
            return $true
        }
    }
    catch {}

    Write-Log "Redis not running, trying to start..." "WARNING"
    $redisPath = Find-RedisServer

    if ($redisPath) {
        try {
            Start-Process -FilePath $redisPath -WindowStyle Hidden -ErrorAction Stop
            Start-Sleep -Seconds 2
            $redisResult = redis-cli ping 2>&1
            if ($redisResult -eq "PONG") {
                Write-Log "Redis started successfully" "SUCCESS"
                return $true
            }
        }
        catch {
            Write-Log "Redis start failed: $_" "ERROR"
        }
    }
    else {
        Write-Log "Redis not found. Please install Redis or ensure redis-server is in PATH" "ERROR"
    }
    return $false
}

function Start-ServiceWithRetry {
    param(
        [string]$Name,
        [string]$Command,
        [string]$PidFile,
        [int]$Port,
        [string]$WorkDir = $PROJECT_ROOT
    )

    Write-Log "Starting $Name..." "INFO"

    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "cmd.exe"
        $startInfo.Arguments = "/c cd /d `"$WorkDir`" && $Command"
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $false
        $startInfo.RedirectStandardError = $false
        $startInfo.CreateNoWindow = $false

        $process = [System.Diagnostics.Process]::Start($startInfo)
        $process.Id | Out-File -FilePath $PidFile -Encoding UTF8

        Start-Sleep -Seconds 3

        if (-not $process.HasExited) {
            Write-Log "$Name started (PID: $($process.Id))" "SUCCESS"
            return $true
        }
        else {
            Write-Log "$Name exited immediately with code $($process.ExitCode)" "ERROR"
            return $false
        }
    }
    catch {
        Write-Log "$Name failed to start: $_" "ERROR"
        return $false
    }
}

function Wait-ForService {
    param([string]$Url, [int]$Timeout = 15, [string]$Name = "Service")
    for ($i = 0; $i -lt $Timeout; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

function Save-Config {
    param([hashtable]$Config)
    $Config | ConvertTo-Json | Out-File -FilePath $CONFIG_FILE -Encoding UTF8
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   AutoClip Startup Script             " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

if (-not $SkipStop) {
    Stop-AllServices
    Start-Sleep -Seconds 2
}

if (-not $SkipRedis) {
    Write-Log "========== Redis Check ==========" "INFO"
    $redisOk = Start-RedisService
    if (-not $redisOk) {
        $continue = Read-Host "Redis failed to start, continue anyway? (y/N)"
        if ($continue -ne "y" -and $continue -ne "Y") {
            exit 1
        }
    }
}
else {
    Write-Log "Skipping Redis check" "INFO"
}

Write-Log "========== Port Detection ==========" "INFO"

$actualBackendPort = $BackendPort
if (-not (Test-PortAvailable -Port $BackendPort)) {
    Write-Log "Port $BackendPort is in use, killing the process..." "WARNING"
    Kill-ProcessByPort -Port $BackendPort
}
Write-Log "Backend port: $actualBackendPort" "SUCCESS"

$actualFrontendPort = $FrontendPort
if (-not (Test-PortAvailable -Port $FrontendPort)) {
    Write-Log "Port $FrontendPort is in use, killing the process..." "WARNING"
    Kill-ProcessByPort -Port $FrontendPort
}
Write-Log "Frontend port: $actualFrontendPort" "SUCCESS"

Save-Config -Config @{
    backendPort = $actualBackendPort
    frontendPort = $actualFrontendPort
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}

$env:PYTHONPATH = $PROJECT_ROOT

Write-Host ""
Write-Log "========== Starting Backend ==========" "INFO"
$pythonExe = Join-Path $PROJECT_ROOT "venv\Scripts\python.exe"
$backendCmd = "$pythonExe -m uvicorn backend.main:app --host 0.0.0.0 --port $actualBackendPort --reload"
Start-ServiceWithRetry -Name "Backend" -Command $backendCmd -PidFile $BACKEND_PID_FILE -Port $actualBackendPort

$backendOk = Wait-ForService -Url "http://localhost:$actualBackendPort/api/v1/projects/" -Timeout 15 -Name "Backend"
if ($backendOk) {
    Write-Log "Backend health check passed" "SUCCESS"
}
else {
    Write-Log "Backend may not have started properly" "WARNING"
}

Write-Host ""
Write-Log "========== Starting Frontend ==========" "INFO"
$frontendDir = Join-Path $PROJECT_ROOT "frontend"
$frontendCmd = "npm run dev -- --host 0.0.0.0 --port $actualFrontendPort"
Start-ServiceWithRetry -Name "Frontend" -Command $frontendCmd -PidFile $FRONTEND_PID_FILE -Port $actualFrontendPort -WorkDir $frontendDir

$frontendOk = Wait-ForService -Url "http://localhost:$actualFrontendPort" -Timeout 20 -Name "Frontend"
if ($frontendOk) {
    Write-Log "Frontend started successfully" "SUCCESS"
}
else {
    Write-Log "Frontend may not have started properly" "WARNING"
}

Write-Host ""
Write-Log "========== Starting Celery Worker ==========" "INFO"
$celeryExe = Join-Path $PROJECT_ROOT "venv\Scripts\python.exe"
$celeryCmd = "$celeryExe -m celery -A backend.core.celery_app worker --loglevel=info --concurrency=1 --pool=solo -Q processing,upload,notification,maintenance"
Start-ServiceWithRetry -Name "Celery Worker" -Command $celeryCmd -PidFile $CELERY_PID_FILE -Port 0

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "            Startup Complete!          " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:  http://localhost:$actualFrontendPort" -ForegroundColor Cyan
Write-Host "  Backend:   http://localhost:$actualBackendPort" -ForegroundColor Cyan
Write-Host "  API Docs:  http://localhost:$actualBackendPort/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Stop:      .\stop_autoclip.ps1" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""