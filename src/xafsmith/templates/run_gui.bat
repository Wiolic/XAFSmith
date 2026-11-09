@echo off
chcp 65001 >nul
rem 双击打开本项目的 XAFSmith（桌面窗口）
set "PYW="
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\XAFSmith\location.txt" (
  set /p LOC=<"%LOCALAPPDATA%\XAFSmith\location.txt"
)
if not defined PYW if defined LOC set "PYW=%LOC%\venv\Scripts\pythonw.exe"
if not defined PYW (
  echo 没有找到 XAFSmith：请先运行软件包中的 安装XAFSmith.bat
  pause
  exit /b 1
)
start "" "%PYW%" -m xafsmith gui --project "%~dp0."
