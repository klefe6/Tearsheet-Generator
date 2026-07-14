$ErrorActionPreference = 'Stop'
Write-Error @"
Refusing to start AGM staff from the dirty Tearsheet Generator checkout.
Use: C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_mp_staff.bat
"@
exit 1
