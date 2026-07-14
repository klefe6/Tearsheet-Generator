$ErrorActionPreference = 'Stop'
Write-Error @"
Refusing to start production TCP from the dirty Tearsheet Generator checkout.
Use the canonical runtime launcher instead:
  C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_tcp_ts.bat
Configured via: C:\Coding Projects\Manager\tearsheet_fleet_runtime.json
"@
exit 1
