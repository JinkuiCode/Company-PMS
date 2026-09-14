@echo off
setlocal
chcp 65001 >nul
echo This compatibility entry now uses the standard PMS Windows operations module.
call "%~dp0pms-auto-start.bat"
exit /b %ERRORLEVEL%
