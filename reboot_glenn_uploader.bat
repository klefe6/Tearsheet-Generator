@echo off
REM Glenn Daily Uploader - Full Stack Reboot Script
REM Frontend: Vite (port 5173)
REM Backend: FastAPI (port 8091)
REM Component output is appended to Manager\logs so boot-time failures
REM stay diagnosable (the inner start windows escape any outer redirect).

cd /d "%~dp0"

set "GLENN_LOG_DIR=C:\Coding Projects\Manager\logs"
if not exist "%GLENN_LOG_DIR%" mkdir "%GLENN_LOG_DIR%"
set "GLENN_BE_LOG=%GLENN_LOG_DIR%\Glenn_Uploader_backend.log"
set "GLENN_FE_LOG=%GLENN_LOG_DIR%\Glenn_Uploader_frontend.log"

echo Stopping Glenn Uploader services...
REM /C:":5173 " = exact port token (trailing space) so e.g. :51730 never matches.
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":8091 " ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul

timeout /t 2 /nobreak >nul

echo ==== Glenn Uploader backend start %date% %time% ====>>"%GLENN_BE_LOG%"
echo Starting Glenn Uploader Backend on port 8091...
cd uploader\backend
start "Glenn Uploader Backend" cmd /k "call start_dev.bat >> "%GLENN_BE_LOG%" 2>&1"
cd ..\..

timeout /t 5 /nobreak >nul

echo ==== Glenn Uploader frontend start %date% %time% ====>>"%GLENN_FE_LOG%"
echo Starting Glenn Uploader Frontend on port 5173...
cd uploader\frontend
start "Glenn Uploader Frontend" cmd /k "npm run dev >> "%GLENN_FE_LOG%" 2>&1"
cd ..\..

echo.
echo ========================================
echo Glenn Uploader start commands issued.
echo ========================================
echo Frontend: http://127.0.0.1:5173   (log: %GLENN_FE_LOG%)
echo Backend:  http://127.0.0.1:8091   (log: %GLENN_BE_LOG%)
echo API:      http://127.0.0.1:8091/api
echo ========================================
