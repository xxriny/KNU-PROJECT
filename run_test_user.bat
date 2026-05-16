@echo off

:: Move to script directory
cd /d "%~dp0"

:: Set Session Directory
set "TEST_USER_DIR=%~dp0backend\storage\test_user_session"
if not exist "%TEST_USER_DIR%" mkdir "%TEST_USER_DIR%"

echo Starting NAVIGATOR for Test User...
echo Session: %TEST_USER_DIR%
echo.

:: Execute Electron via NPX directly
:: We use 'call' to keep the batch alive and 'pause' if it fails
call npx electron . --user-data-dir="%TEST_USER_DIR%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application failed to start.
    echo Error Code: %errorlevel%
    pause
)
