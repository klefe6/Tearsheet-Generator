@echo off
REM Glenn Daily Uploader - Full Stack Reboot Script
REM Frontend: Vite (port 5173)      -> glenn_uploader_frontend_logged.bat
REM Backend: FastAPI (port 8091)    -> glenn_uploader_backend_logged.bat
REM Component output is appended to Manager\logs via the *_logged.bat shims so
REM boot-time failures stay diagnosable (inner start windows escape any outer
REM redirect, and inline nested-quote redirects are mangled by cmd).

cd /d "%~dp0"

echo Stopping Glenn Uploader services...
REM /C:":5173 " = exact port token (trailing space) so e.g. :51730 never matches.
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":8091 " ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul

timeout /t 2 /nobreak >nul

REM .\ prefix = explicit cwd path, immune to NoDefaultCurrentDirectoryInExePath.
echo Starting Glenn Uploader Backend on port 8091...
start "Glenn Uploader Backend" cmd /k call .\glenn_uploader_backend_logged.bat

timeout /t 5 /nobreak >nul

echo Starting Glenn Uploader Frontend on port 5173...
start "Glenn Uploader Frontend" cmd /k call .\glenn_uploader_frontend_logged.bat

echo.
echo ========================================
echo Glenn Uploader start commands issued.
echo ========================================
echo Frontend: http://127.0.0.1:5173   (log: Manager\logs\Glenn_Uploader_frontend.log)
echo Backend:  http://127.0.0.1:8091   (log: Manager\logs\Glenn_Uploader_backend.log)
echo API:      http://127.0.0.1:8091/api
echo ========================================
