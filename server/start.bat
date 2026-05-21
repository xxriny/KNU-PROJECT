@echo off
setlocal
title NAVIGATOR Server
cd /d "%~dp0"

echo ================================================
echo  NAVIGATOR Server (Auth / Billing / Gemini Key)
echo ================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Python 3.11+ required.
        pause
        exit /b 1
    )
)

echo [2/3] Installing / updating dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo [3/3] Starting NAVIGATOR Server on port 8001...
echo.
echo  Endpoints:
echo    Auth    : http://localhost:8001/auth/*
echo    Billing : http://localhost:8001/billing/*
echo    Keys    : http://localhost:8001/keys/*
echo    Docs    : http://localhost:8001/docs
echo.
echo  Press Ctrl+C to stop.
echo ================================================

python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

:end
echo.
echo Server stopped.
pause
