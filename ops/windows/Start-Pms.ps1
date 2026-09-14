param([string]$ConfigPath = "$PSScriptRoot\pms-operations.json")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module "$PSScriptRoot\PmsOperations.psm1" -Force
$config = Get-PmsConfig -ConfigPath $ConfigPath
Initialize-PmsDataRoot -Config $config

& "$PSScriptRoot\Rotate-PmsLogs.ps1" -ConfigPath $ConfigPath

$previousConfigFile = $env:PMS_CONFIG_FILE
try {
    $env:PMS_CONFIG_FILE = $config.protectedConfig
    Push-Location "$($config.installRoot)\backend"
    try {
        & $config.pythonExe "scripts\check_runtime_config.py" --expect production
        if ($LASTEXITCODE -ne 0) { throw "PMS protected configuration validation failed." }
    } finally {
        Pop-Location
    }
} finally {
    $env:PMS_CONFIG_FILE = $previousConfigFile
}

$backendPidFile = "$($config.dataRoot)\pids\backend.pid"
$backendPid = Get-PmsPid -Path $backendPidFile
$backendOwned = $backendPid -and (Assert-PmsOwnedProcess -ProcessId $backendPid -ExpectedExecutable $config.pythonExe -CommandContains "main:app")
if (-not $backendOwned) {
    Remove-Item -LiteralPath $backendPidFile -Force -ErrorAction SilentlyContinue
    $environment = @{ PMS_CONFIG_FILE = [string]$config.protectedConfig }
    $oldConfigFile = $env:PMS_CONFIG_FILE
    $env:PMS_CONFIG_FILE = $environment.PMS_CONFIG_FILE
    try {
        $backend = Start-Process -FilePath $config.pythonExe `
            -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", [string]$config.backendPort) `
            -WorkingDirectory "$($config.installRoot)\backend" `
            -RedirectStandardOutput "$($config.dataRoot)\logs\backend.log" `
            -RedirectStandardError "$($config.dataRoot)\logs\backend-error.log" `
            -WindowStyle Hidden -PassThru
        Set-Content -LiteralPath $backendPidFile -Value $backend.Id -Encoding ASCII
    } finally {
        $env:PMS_CONFIG_FILE = $oldConfigFile
    }
}

$webHealthy = $false
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($config.webPort)/" -TimeoutSec 3
    $webHealthy = $response.StatusCode -eq 200
} catch {}

if (-not $webHealthy) {
    Start-Process -FilePath $config.nginxExe `
        -ArgumentList @("-p", $config.nginxRoot, "-c", $config.nginxConfig) `
        -WorkingDirectory $config.nginxRoot -WindowStyle Hidden | Out-Null
}

$deadline = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($config.backendPort)/api/health" -TimeoutSec 3
        if ($health.status -eq "ok") { exit 0 }
    } catch {}
} while ((Get-Date) -lt $deadline)

throw "PMS backend did not become healthy within 30 seconds."
