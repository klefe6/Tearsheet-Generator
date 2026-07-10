@echo off
REM Start Glenn Daily Uploader backend on port 8091 (see docs/LOCAL_DEV.md).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1"
