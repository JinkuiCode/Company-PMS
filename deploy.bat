@echo off
chcp 65001 >nul
echo ============================================
echo   PMS 项目管理系统 - 一键部署脚本
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.13 并添加到 PATH
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 20 LTS
    pause
    exit /b 1
)

echo [1/5] 安装后端依赖...
cd /d "%~dp0backend"
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/5] 安装前端依赖...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/5] 构建前端生产包...
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    pause
    exit /b 1
)

echo.
echo [4/5] 下载 nssm（Windows 服务管理工具）...
cd /d "%~dp0"
if not exist "nssm.exe" (
    echo 请手动下载 nssm: https://nssm.cc/download
    echo 将 nssm.exe 放到 %~dp0 目录下
    echo 然后重新运行此脚本
    echo.
    echo [跳过] 服务注册步骤，请先获取 nssm
) else (
    echo 注册后端服务...
    nssm install PMS-Backend "C:\Program Files\Python313\python.exe" "-m uvicorn main:app --host 127.0.0.1 --port 8000"
    nssm set PMS-Backend AppDirectory "%~dp0backend"
    nssm set PMS-Backend DisplayName "PMS Backend API"
    nssm set PMS-Backend Description "PMS FastAPI Backend Service"
    nssm set PMS-Backend Start SERVICE_AUTO_START
    nssm start PMS-Backend
    echo 后端服务已注册并启动
)

echo.
echo [5/5] 部署完成！
echo ============================================
echo.
echo 前端构建产物: %~dp0frontend\dist\
echo 后端 API 地址: http://127.0.0.1:8000
echo.
echo 接下来请配置 Nginx:
echo   1. 静态文件指向 frontend\dist\
echo   2. /api/* 反向代理到 http://127.0.0.1:8000
echo.
echo Nginx 配置示例已生成: %~dp0nginx_pms.conf
echo ============================================
pause
