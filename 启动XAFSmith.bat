@echo off
chcp 65001 >nul
rem 双击启动 XAFSmith（桌面窗口，不使用浏览器）
set "LOC="
if exist "%LOCALAPPDATA%\XAFSmith\location.txt" set /p LOC=<"%LOCALAPPDATA%\XAFSmith\location.txt"
if not defined LOC (
  echo 还没有安装：请先双击 安装XAFSmith.bat
  pause
  exit /b 1
)
start "" "%LOC%\venv\Scripts\pythonw.exe" -m xafsmith gui
