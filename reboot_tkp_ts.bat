@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reboot_tkp_ts.ps1"
