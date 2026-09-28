@echo off
REM Shim: run the Glenn Uploader frontend (Vite, port 5173) with output
REM appended to Manager\logs. See glenn_uploader_backend_logged.bat for why.
set "GLENN_LOG_DIR=C:\Coding Projects\Manager\logs"
if not exist "%GLENN_LOG_DIR%" mkdir "%GLENN_LOG_DIR%"
set "GLENN_FE_LOG=%GLENN_LOG_DIR%\Glenn_Uploader_frontend.log"
cd /d "%~dp0uploader\frontend"
echo ==== Glenn Uploader frontend start %date% %time% ====>>"%GLENN_FE_LOG%"
call npm run dev >> "%GLENN_FE_LOG%" 2>&1
