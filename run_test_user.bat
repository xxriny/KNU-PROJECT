@echo off
setlocal
title NAVIGATOR (Test User)

cd /d "%~dp0"

:: Set Session Directory
set "TEST_USER_DIR=%~dp0backend\storage\test_user_session"
if not exist "%TEST_USER_DIR%" mkdir "%TEST_USER_DIR%"

echo Starting NAVIGATOR for Test User...
echo Session: %TEST_USER_DIR%
echo.

echo [1/3] Checking if Vite is already running...
powershell -Command "try { $c = New-Object System.Net.Sockets.TcpClient('localhost', 5173); if ($c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo Vite is already running on port 5173. Skipping startup.
    goto launch_electron
)

echo [2/3] Starting Vite dev server...
set LOGFILE=vite_test_%RANDOM%.log
start /b cmd /c "npm run dev:vite > %LOGFILE% 2>&1"

echo Waiting for Vite on port 5173...
set /a VITE_WAIT_COUNT=0
set /a VITE_WAIT_MAX=90
:wait_vite
powershell -Command "try { $c = New-Object System.Net.Sockets.TcpClient('localhost', 5173); if ($c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% neq 0 (
    set /a VITE_WAIT_COUNT+=1
    if %VITE_WAIT_COUNT% geq %VITE_WAIT_MAX% (
        echo [ERROR] Vite did not open port 5173 within %VITE_WAIT_MAX% seconds.
        goto cleanup
    )
    timeout /t 1 /nobreak >nul
    goto wait_vite
)
echo Vite is ready!

:launch_electron
echo [3/3] Launching Electron (test user session)...
call npx electron . --user-data-dir="%TEST_USER_DIR%"

:cleanup
pause
