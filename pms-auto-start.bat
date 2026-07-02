@echo off
chcp 65001 >nul

set LOGFILE=D:\Code\Company-PMS\pms-startup.log
echo ============================================ >> "%LOGFILE%"
echo   PMS Auto Start %date% %time% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"

echo [0/4] Waiting 30s... >> "%LOGFILE%"
timeout /t 30 /nobreak >nul

echo [1/4] Checking port 8000... >> "%LOGFILE%"
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -notmatch 'python') { Stop-Process -Id $_.OwningProcess -Force; Write-Output ('Killed PID ' + $_.OwningProcess + ' ' + $p.ProcessName) } }" >> "%LOGFILE%" 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Checking MSSQL... >> "%LOGFILE%"
"C:\Program Files\Python313\python.exe" -c "import pyodbc; pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.10.1.149;PORT=1433;DATABASE=PMS;UID=sa-jinky;PWD=Qwerty1234.')" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] MSSQL failed >> "%LOGFILE%"
) else (
    echo   MSSQL OK >> "%LOGFILE%"
)

echo [3/4] Starting backend... >> "%LOGFILE%"
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "Start-Process -FilePath 'C:\Program Files\Python313\python.exe' -ArgumentList '-m uvicorn main:app --host 0.0.0.0 --port 8000' -WorkingDirectory 'D:\Code\Company-PMS\backend' -WindowStyle Hidden"
echo   Backend started >> "%LOGFILE%"

echo [4/4] Starting frontend... >> "%LOGFILE%"
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "Start-Process -FilePath 'D:\Program Files\nodejs\npx.cmd' -ArgumentList 'vite --host 0.0.0.0 --port 5174' -WorkingDirectory 'D:\Code\Company-PMS\frontend' -WindowStyle Hidden"
echo   Frontend started >> "%LOGFILE%"

echo ============================================ >> "%LOGFILE%"
echo   Done %date% %time% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"
