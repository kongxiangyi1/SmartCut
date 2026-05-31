@echo off
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo        SmartCut Stop Script (BAT Version)
echo ===============================================
echo.

echo [1/3] Cleaning PID files...
del /f /q "%~dp0*.pid" 2>NUL

echo.
echo [2/3] Stopping processes...
echo Killing Python processes...
taskkill /f /im python.exe 2>NUL
echo Killing Node processes...
taskkill /f /im node.exe 2>NUL
echo Killing Celery processes...
taskkill /f /im celery.exe 2>NUL
echo Killing uvicorn processes...
taskkill /f /im uvicorn.exe 2>NUL

echo.
echo [3/3] Checking status...
echo.

set "all_clear=1"

:: Check port 8090
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8090 "') do (
    if not "%%a"=="0" (
        set "all_clear=0"
        echo WARNING: Port 8090 is still in use by PID %%a
    )
)

:: Check port 3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do (
    if not "%%a"=="0" (
        set "all_clear=0"
        echo WARNING: Port 3000 is still in use by PID %%a
    )
)

:: Check port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do (
    if not "%%a"=="0" (
        set "all_clear=0"
        echo WARNING: Port 8000 is still in use by PID %%a
    )
)

:: Check port 5555
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5555 "') do (
    if not "%%a"=="0" (
        set "all_clear=0"
        echo WARNING: Port 5555 is still in use by PID %%a
    )
)

echo.
if !all_clear! equ 1 (
    echo SUCCESS: All services stopped!
) else (
    echo WARNING: Some ports are still in use.
    echo You may need to restart your computer.
)

echo.
echo ===============================================
echo.
