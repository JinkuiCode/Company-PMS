@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "OPS=%ROOT%ops\windows"

if not exist "%OPS%\pms-operations.json" (
    echo Missing %OPS%\pms-operations.json
    echo Create it from pms-operations.example.json before starting PMS.
    exit /b 1
)

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" ^
    -NoProfile -ExecutionPolicy Bypass ^
    -File "%OPS%\Start-Pms.ps1" ^
    -ConfigPath "%OPS%\pms-operations.json"
exit /b %ERRORLEVEL%
