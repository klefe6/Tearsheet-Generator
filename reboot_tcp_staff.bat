@echo on
setlocal
rem Refuse staff launch from the dirty Tearsheet Generator checkout.
for %%I in ("%~dp0.") do set "HERE=%%~fI"
if /I "%HERE%"=="C:\Coding Projects\Tearsheet Generator" (
  echo Refusing to start TCP staff from the dirty Tearsheet Generator checkout:
  echo   %HERE%
  echo Use the canonical runtime:
  echo   C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_tcp_staff.bat
  echo Configured via: C:\Coding Projects\Manager\tearsheet_fleet_runtime.json
  exit /b 1
)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reboot_tcp_staff.ps1"
