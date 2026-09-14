param([string]$ConfigPath = "$PSScriptRoot\pms-operations.json")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module "$PSScriptRoot\PmsOperations.psm1" -Force
$config = Get-PmsConfig -ConfigPath $ConfigPath
Initialize-PmsDataRoot -Config $config
$logDir = "$($config.dataRoot)\logs"
$limit = [int64]$config.maxLogSizeMb * 1MB
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

Get-ChildItem -LiteralPath $logDir -Filter "*.log" -File | ForEach-Object {
    if ($_.Length -ge $limit) {
        Move-Item -LiteralPath $_.FullName -Destination "$($_.FullName).$stamp.archive"
    }
}
Get-ChildItem -LiteralPath $logDir -Filter "*.archive" -File | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-[int]$config.logRetentionDays)
} | Remove-Item -Force
