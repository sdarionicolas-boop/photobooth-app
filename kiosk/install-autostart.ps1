<#
.SYNOPSIS
  Registers (or removes) a scheduled task that runs start-kiosk.ps1 when the current user logs on.

.DESCRIPTION
  Run once on the mirror PC. Pair it with Windows automatic sign-in (netplwiz) so the mirror
  comes up by itself after a power cut. Needs no admin rights (task runs as the current user).

.PARAMETER Remove
  Unregister the task again.
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'PhotoboothMirrorKiosk'

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "removed task $TaskName"
    return
}

$script = Join-Path $PSScriptRoot 'start-kiosk.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "registered task ${TaskName}: runs $script at logon of $env:USERNAME"
Write-Host "remove with: .\install-autostart.ps1 -Remove"
