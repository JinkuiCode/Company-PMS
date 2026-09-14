param([string]$ConfigPath = "$PSScriptRoot\pms-operations.json")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module "$PSScriptRoot\PmsOperations.psm1" -Force
$config = Get-PmsConfig -ConfigPath $ConfigPath

$backendPidFile = "$($config.dataRoot)\pids\backend.pid"
$backendPid = Get-PmsPid -Path $backendPidFile
if ($backendPid) {
    if (-not (Assert-PmsOwnedProcess -ProcessId $backendPid -ExpectedExecutable $config.pythonExe -CommandContains "main:app")) {
        throw "Refusing to stop PID $backendPid because it is not the managed PMS backend."
    }
    Stop-Process -Id $backendPid
    Remove-Item -LiteralPath $backendPidFile -Force -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $config.nginxExe) {
    & $config.nginxExe -p $config.nginxRoot -c $config.nginxConfig -s quit
}
