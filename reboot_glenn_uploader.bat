@echo off
REM Glenn Daily Uploader - Full Stack Reboot Script
REM Frontend: Vite (port 5173)
REM Backend: FastAPI (port 8091)

cd /d "%~dp0"

echo Stopping Glenn Uploader services...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8091" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul

timeout /t 2 /nobreak >nul

echo Starting Glenn Uploader Backend on port 8091...
cd uploader\backend
start "Glenn Uploader Backend" cmd /k call start_dev.bat
cd ..\..

timeout /t 5 /nobreak >nul

echo Starting Glenn Uploader Frontend on port 5173...
cd uploader\frontend
start "Glenn Uploader Frontend" cmd /k npm run dev
cd ..\..

echo.
echo ========================================
echo Glenn Uploader started successfully!
echo ========================================
echo Frontend: http://127.0.0.1:5173
echo Backend:  http://127.0.0.1:8091
echo API:      http://127.0.0.1:8091/api
echo ========================================
