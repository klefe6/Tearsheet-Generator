$ErrorActionPreference = 'Stop'
Write-Error @"
Refusing to start TCP staff from the dirty Tearsheet Generator checkout.
Use: C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_tcp_staff.bat
"@
exit 1
