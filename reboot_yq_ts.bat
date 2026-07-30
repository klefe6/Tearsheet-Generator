@echo on
setlocal
rem Refuse Y&Q launch from the dirty Tearsheet Generator checkout.
for %%I in ("%~dp0.") do set "HERE=%%~fI"
if /I "%HERE%"=="C:\Coding Projects\Tearsheet Generator" (
  echo Refusing to start Y&Q from the dirty Tearsheet Generator checkout:
  echo   %HERE%
  echo Use the canonical runtime:
  echo   C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_yq_ts.bat
  exit /b 1
)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reboot_yq_ts.ps1"
