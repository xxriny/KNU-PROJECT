"""run_v2.bat 파일을 순수 ASCII로 생성하는 스크립트"""
import os

bat_content = (
    "@echo off\r\n"
    "setlocal\r\n"
    "title PM Agent Pipeline v2\r\n"
    "\r\n"
    "cd /d \"%~dp0\"\r\n"
    "\r\n"
    "echo [1/4] Killing old processes...\r\n"
    "taskkill /f /im node.exe /t 2>nul\r\n"
    "taskkill /f /im python.exe /t 2>nul\r\n"
    "taskkill /f /im electron.exe /t 2>nul\r\n"
    "\r\n"
    "echo [2/4] Starting Vite dev server...\r\n"
    "start /b cmd /c \"npm run dev:vite > vite.log 2>&1\"\r\n"
    "\r\n"
    "echo [3/4] Waiting for Vite on port 5173...\r\n"
    ":wait_vite\r\n"
    "powershell -Command \"try { $c = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 5173); if ($c.Connected) { $c.Close(); exit 0 } } catch { exit 1 }\"\r\n"
    "if %errorlevel% neq 0 (\r\n"
    "    timeout /t 1 /nobreak >nul\r\n"
    "    goto wait_vite\r\n"
    ")\r\n"
    "echo [3/4] Vite is ready!\r\n"
    "\r\n"
    "echo [4/4] Launching Electron app...\r\n"
    "npm run dev:electron\r\n"
    "\r\n"
    "echo Cleaning up...\r\n"
    "taskkill /f /im node.exe /t 2>nul\r\n"
    "taskkill /f /im python.exe /t 2>nul\r\n"
    "echo Done.\r\n"
    "pause\r\n"
)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_v2.bat")
with open(out_path, "wb") as f:
    f.write(bat_content.encode("ascii"))

print(f"Written: {out_path}")
print(f"Size: {os.path.getsize(out_path)} bytes")
print("All ASCII:", bat_content.isascii())
