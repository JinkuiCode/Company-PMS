from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops" / "windows"


def read(name: str) -> str:
    path = OPS / name
    assert path.exists(), f"missing Windows operations file: {name}"
    return path.read_text(encoding="utf-8")


def test_windows_operations_package_is_complete() -> None:
    expected = {
        "PmsOperations.psm1",
        "Start-Pms.ps1",
        "Stop-Pms.ps1",
        "Test-PmsHealth.ps1",
        "Rotate-PmsLogs.ps1",
        "Install-PmsTasks.ps1",
        "Export-PmsOperationsBackup.ps1",
        "pms-operations.example.json",
        "README.md",
    }
    assert expected.issubset({path.name for path in OPS.iterdir()})
    assert "ops/windows/pms-operations.json" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_process_shutdown_is_scoped_to_pms_owned_processes() -> None:
    module = read("PmsOperations.psm1")
    stop = read("Stop-Pms.ps1")
    assert "Assert-PmsOwnedProcess" in module
    assert "Win32_Process" in module
    assert "Stop-Process" in stop
    assert "taskkill /F /IM" not in stop
    assert "Get-Process nginx" not in stop


def test_health_monitor_does_not_auto_restart_by_default() -> None:
    health = read("Test-PmsHealth.ps1")
    config = read("pms-operations.example.json")
    assert '"autoRestart": false' in config
    assert "AutoRestart" in health
    assert "consecutiveFailures" in health
    assert "--expect production" in read("Start-Pms.ps1")


def test_scripts_never_embed_or_print_application_secrets() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in OPS.iterdir())
    for forbidden in ("DB_PASSWORD=", "SECRET_KEY=", "SSO_SECRET_KEY=", "K3_APP_SECRET="):
        assert forbidden not in combined
    assert "Get-Content $EnvFile" not in combined


def test_task_schedule_covers_startup_health_and_log_rotation() -> None:
    installer = read("Install-PmsTasks.ps1")
    assert "AtStartup" in installer
    assert "New-ScheduledTaskTrigger" in installer
    assert "Test-PmsHealth.ps1" in installer
    assert "Rotate-PmsLogs.ps1" in installer


def test_backup_resolves_relative_nginx_config_from_nginx_root() -> None:
    backup = read("Export-PmsOperationsBackup.ps1")
    assert "[System.IO.Path]::IsPathRooted" in backup
    assert "Join-Path $config.nginxRoot $config.nginxConfig" in backup
    assert "Copy-Item -LiteralPath $nginxConfigPath" in backup


def test_legacy_windows_launchers_delegate_without_embedded_credentials() -> None:
    combined = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("pms-auto-start.bat", "start-services.bat")
    )
    assert "Start-Pms.ps1" in combined
    assert "pyodbc.connect" not in combined
    assert "PWD=" not in combined


def test_report_config_is_explicit_and_environment_is_restored() -> None:
    start = read('Start-Pms.ps1')
    assert "Properties['purchaseConfig']" in start
    assert '$env:PMS_PURCHASE_CONFIG_FILE = [string]$config.purchaseConfig' in start
    assert '$env:PMS_PURCHASE_CONFIG_FILE = $oldPurchaseConfig' in start
    assert 'Test-Path -LiteralPath $config.purchaseConfig -PathType Leaf' in start


if __name__ == "__main__":
    test_windows_operations_package_is_complete()
    test_process_shutdown_is_scoped_to_pms_owned_processes()
    test_health_monitor_does_not_auto_restart_by_default()
    test_scripts_never_embed_or_print_application_secrets()
    test_task_schedule_covers_startup_health_and_log_rotation()
    test_backup_resolves_relative_nginx_config_from_nginx_root()
    test_legacy_windows_launchers_delegate_without_embedded_credentials()
    test_report_config_is_explicit_and_environment_is_restored()
    print("windows operations contract passed")
