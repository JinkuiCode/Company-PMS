@echo off
chcp 65001 >nul
echo ============================================
echo   PMS 服务启动脚本
echo ============================================

:: 启动 MySQL（如果未运行）
echo [1/3] 检查 MySQL...
"D:\MySQL\mysql-8.0.33-winx64\bin\mysqladmin.exe" -u root -proot123456 --port=3306 ping >nul 2>&1
if %errorlevel% neq 0 (
    echo   正在启动 MySQL...
    start "" /B "D:\MySQL\mysql-8.0.33-winx64\bin\mysqld.exe" --standalone --datadir="D:\MySQL\data" --basedir="D:\MySQL\mysql-8.0.33-winx64" --port=3306
    timeout /t 5 /nobreak >nul
    echo   MySQL 已启动
) else (
    echo   MySQL 已在运行
)

:: 启动后端 uvicorn
echo [2/3] 启动后端服务 (端口 8000)...
cd /d "D:\Code\Company-PMS\backend"
start "" /B "C:\Program Files\Python313\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
echo   后端已启动

:: 启动前端 vite
echo [3/3] 启动前端服务 (端口 5174)...
cd /d "D:\Code\Company-PMS\frontend"
start "" /B npx vite --host 0.0.0.0 --port 5174
echo   前端已启动

echo ============================================
echo   全部服务已启动！
echo   前端: http://10.10.91.60:5174
echo   后端: http://10.10.91.60:8000
echo ============================================
