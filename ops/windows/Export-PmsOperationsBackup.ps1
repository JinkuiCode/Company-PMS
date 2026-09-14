param(
    [string]$ConfigPath = "$PSScriptRoot\pms-operations.json",
    [string]$DestinationRoot = "D:\PMS-Backups"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module "$PSScriptRoot\PmsOperations.psm1" -Force
$config = Get-PmsConfig -ConfigPath $ConfigPath
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destination = Join-Path $DestinationRoot "PMS-operations-$stamp"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$programDestination = "$destination\program"
New-Item -ItemType Directory -Path $programDestination -Force | Out-Null
& robocopy $config.installRoot $programDestination /E /R:1 /W:1 /XD ".git" ".runtime" "data" "logs" /XF ".env.local" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Program backup failed with robocopy code $LASTEXITCODE." }
Copy-Item -LiteralPath $config.nginxConfig -Destination "$destination\nginx.conf"
Copy-Item -LiteralPath $config.protectedConfig -Destination "$destination\protected-config.env"
icacls "$destination\protected-config.env" /inheritance:r /grant:r "SYSTEM:F" "Administrators:F" | Out-Null

foreach ($taskName in @("PMS-Startup", "PMS-Health", "PMS-Log-Rotation")) {
    Export-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Set-Content -LiteralPath "$destination\$taskName.xml" -Encoding UTF8
}
Get-FileHash -Path "$destination\program\backend\main.py", "$destination\nginx.conf" -Algorithm SHA256 |
    ConvertTo-Json | Set-Content -LiteralPath "$destination\manifest.json" -Encoding UTF8
Write-Host "Operations backup created: $destination"
