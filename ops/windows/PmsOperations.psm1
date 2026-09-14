Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PmsConfig {
    param([Parameter(Mandatory = $true)][string]$ConfigPath)
    $resolved = (Resolve-Path -LiteralPath $ConfigPath).Path
    $config = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($name in @("installRoot", "pythonExe", "nginxExe", "protectedConfig", "dataRoot")) {
        if (-not $config.$name) { throw "Missing operations setting: $name" }
    }
    return $config
}

function Initialize-PmsDataRoot {
    param([Parameter(Mandatory = $true)]$Config)
    foreach ($path in @($Config.dataRoot, "$($Config.dataRoot)\logs", "$($Config.dataRoot)\pids", "$($Config.dataRoot)\state")) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

function Get-PmsProcess {
    param([Parameter(Mandatory = $true)][int]$ProcessId)
    return Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Assert-PmsOwnedProcess {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$ExpectedExecutable,
        [string]$CommandContains = ""
    )
    $process = Get-PmsProcess -ProcessId $ProcessId
    if (-not $process) { return $false }
    $actual = [IO.Path]::GetFullPath([string]$process.ExecutablePath)
    $expected = [IO.Path]::GetFullPath($ExpectedExecutable)
    if (-not $actual.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ($CommandContains -and ([string]$process.CommandLine).IndexOf($CommandContains, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }
    return $true
}

function Get-PmsPid {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $value = (Get-Content -LiteralPath $Path -Raw).Trim()
    $pidValue = 0
    if ([int]::TryParse($value, [ref]$pidValue)) { return $pidValue }
    return $null
}

function Write-PmsJsonLog {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$Data
    )
    $record = @{ timestamp = (Get-Date).ToString("o") }
    foreach ($key in $Data.Keys) { $record[$key] = $Data[$key] }
    ($record | ConvertTo-Json -Compress) | Add-Content -LiteralPath $Path -Encoding UTF8
}

Export-ModuleMember -Function Get-PmsConfig, Initialize-PmsDataRoot, Get-PmsProcess, Assert-PmsOwnedProcess, Get-PmsPid, Write-PmsJsonLog
