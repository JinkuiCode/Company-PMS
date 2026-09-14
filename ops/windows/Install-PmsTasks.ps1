param([string]$ConfigPath = "$PSScriptRoot\pms-operations.json")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an elevated PowerShell window."
}

$powerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

$startupAction = New-ScheduledTaskAction -Execute $powerShellExe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\Start-Pms.ps1`" -ConfigPath `"$ConfigPath`""
$startupTrigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "PMS-Startup" -Action $startupAction -Trigger $startupTrigger -Principal $taskPrincipal -Settings $settings -Force | Out-Null

$healthAction = New-ScheduledTaskAction -Execute $powerShellExe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\Test-PmsHealth.ps1`" -ConfigPath `"$ConfigPath`""
$healthTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "PMS-Health" -Action $healthAction -Trigger $healthTrigger -Principal $taskPrincipal -Settings $settings -Force | Out-Null

$rotateAction = New-ScheduledTaskAction -Execute $powerShellExe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\Rotate-PmsLogs.ps1`" -ConfigPath `"$ConfigPath`""
$rotateTrigger = New-ScheduledTaskTrigger -Daily -At "02:10"
Register-ScheduledTask -TaskName "PMS-Log-Rotation" -Action $rotateAction -Trigger $rotateTrigger -Principal $taskPrincipal -Settings $settings -Force | Out-Null

Write-Host "PMS startup, health, and log rotation tasks were registered."
