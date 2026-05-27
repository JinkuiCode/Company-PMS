@echo off
chcp 65001 >nul
echo ============================================
echo   PMS 服务启动脚本
echo ============================================

:: 检查 MSSQL 连接（远程服务器，无需本地启动）
echo [1/3] 检查 MSSQL 连接...
"C:\Program Files\Python313\python.exe" -c "import pyodbc; pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.10.1.149;PORT=1433;DATABASE=PMS;UID=sa-jinky;PWD=Qwerty1234.')" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [警告] 无法连接 MSSQL 服务器 10.10.1.149:1433
) else (
    echo   MSSQL 连接正常
)

:: 启动后端 uvicorn
echo [2/3] 启动后端服务 (端口 8000)...
cd /d "D:\Code\Company-PMS\backend"
start "" /B "C:\Program Files\Python313\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
echo   后端已启动

:: 启动前端 vite
echo [3/3] 启动前端服务 (端口 5174)...
cd /d "D:\Code\Company-PMS\frontend"
start "" /B "D:\Program Files\nodejs\npx.cmd" vite --host 0.0.0.0 --port 5174
echo   前端已启动

echo ============================================
echo   全部服务已启动！
echo   前端: http://10.10.91.60:5174
echo   后端: http://10.10.91.60:8000
echo ============================================
