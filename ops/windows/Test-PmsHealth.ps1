param(
    [string]$ConfigPath = "$PSScriptRoot\pms-operations.json",
    [switch]$AutoRestart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module "$PSScriptRoot\PmsOperations.psm1" -Force
$config = Get-PmsConfig -ConfigPath $ConfigPath
Initialize-PmsDataRoot -Config $config

$statePath = "$($config.dataRoot)\state\health.json"
$logPath = "$($config.dataRoot)\logs\health.log"
$state = @{ consecutiveFailures = 0 }
if (Test-Path -LiteralPath $statePath) {
    try {
        $savedState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $state.consecutiveFailures = [int]$savedState.consecutiveFailures
    } catch {}
}

$backendHealthy = $false
$webHealthy = $false
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($config.backendPort)/api/health" -TimeoutSec 5
    $backendHealthy = $health.status -eq "ok"
} catch {}
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($config.webPort)/" -TimeoutSec 5
    $webHealthy = $response.StatusCode -eq 200
} catch {}

if ($backendHealthy -and $webHealthy) {
    $state.consecutiveFailures = 0
    $status = "healthy"
} else {
    $state.consecutiveFailures = [int]$state.consecutiveFailures + 1
    $status = "unhealthy"
}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
Write-PmsJsonLog -Path $logPath -Data @{
    status = $status
    backend = $backendHealthy
    web = $webHealthy
    consecutiveFailures = $state.consecutiveFailures
}

$restartEnabled = $AutoRestart -or [bool]$config.autoRestart
if ($status -eq "unhealthy" -and $restartEnabled -and $state.consecutiveFailures -ge [int]$config.restartAfterFailures) {
    & "$PSScriptRoot\Stop-Pms.ps1" -ConfigPath $ConfigPath
    & "$PSScriptRoot\Start-Pms.ps1" -ConfigPath $ConfigPath
}
if ($status -eq "unhealthy") { exit 1 }
exit 0
