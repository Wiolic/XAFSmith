@echo off
chcp 65001 >nul
title XAFSmith
set "XS=%LOCALAPPDATA%\XAFSmith\venv\Scripts\xafsmith.exe"
if not exist "%XS%" (
  echo 还没有安装：请先双击 安装XAFSmith.bat
  pause
  exit /b 1
)
echo 正在启动 XAFSmith，浏览器会自动打开 http://localhost:8501
echo 使用期间不要关闭本窗口；关闭本窗口即退出软件。
cd /d "%USERPROFILE%"
"%XS%" gui
pause
