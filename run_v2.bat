@echo off
setlocal
title PM Agent Pipeline v2

cd /d "%~dp0"

echo [1/4] Killing old processes...
taskkill /f /im node.exe /t 2>nul
taskkill /f /im python.exe /t 2>nul
taskkill /f /im electron.exe /t 2>nul

echo [2/4] Starting Vite dev server...
start /b cmd /c "npm run dev:vite > vite.log 2>&1"

echo [3/4] Waiting for Vite on port 5173...
set /a VITE_WAIT_COUNT=0
set /a VITE_WAIT_MAX=90
:wait_vite
powershell -Command "try { $c = New-Object System.Net.Sockets.TcpClient('localhost', 5173); if ($c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% neq 0 (
    set /a VITE_WAIT_COUNT+=1
    if %VITE_WAIT_COUNT% geq %VITE_WAIT_MAX% (
        echo [ERROR] Vite did not open port 5173 within %VITE_WAIT_MAX% seconds.
        echo [ERROR] Last lines of vite.log:
        powershell -Command "if (Test-Path 'vite.log') { Get-Content -Path 'vite.log' -Tail 40 } else { Write-Host 'vite.log not found' }"
        goto cleanup
    )
    timeout /t 1 /nobreak >nul
    goto wait_vite
)
echo [3/4] Vite is ready!

echo [4/4] Launching Electron app...
npm run dev:electron

:cleanup
echo Cleaning up...
taskkill /f /im node.exe /t 2>nul
taskkill /f /im python.exe /t 2>nul
echo Done.
pause
