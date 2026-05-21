@echo off
setlocal
title NAVIGATOR Server
cd /d "%~dp0"

echo ================================================
echo  NAVIGATOR Server (Auth / Billing / Gemini Key)
echo ================================================
echo.

REM ── 가상환경 확인 및 생성 ─────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python 3.11+ is installed.
        pause
        exit /b 1
    )
)

REM ── 의존성 설치 ───────────────────────────────────────────────
echo [2/3] Installing / updating dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

REM ── 서버 시작 ─────────────────────────────────────────────────
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
