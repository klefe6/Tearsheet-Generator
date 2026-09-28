@echo off
REM Shim: run the Glenn Uploader backend with output appended to Manager\logs.
REM Exists so reboot_glenn_uploader.bat's `start` line needs no nested quotes
REM (cmd's quote-stripping mangles `start ... cmd /k "call x >> "log""` lines).
set "GLENN_LOG_DIR=C:\Coding Projects\Manager\logs"
if not exist "%GLENN_LOG_DIR%" mkdir "%GLENN_LOG_DIR%"
set "GLENN_BE_LOG=%GLENN_LOG_DIR%\Glenn_Uploader_backend.log"
cd /d "%~dp0uploader\backend"
echo ==== Glenn Uploader backend start %date% %time% ====>>"%GLENN_BE_LOG%"
call .\start_dev.bat >> "%GLENN_BE_LOG%" 2>&1
