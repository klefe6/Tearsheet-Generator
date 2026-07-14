@echo off
setlocal
echo Refusing to start production TCP from the dirty Tearsheet Generator checkout.
echo Use the canonical runtime launcher instead:
echo   "C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_tcp_ts.bat"
echo Configured via: C:\Coding Projects\Manager\tearsheet_fleet_runtime.json
exit /b 1
