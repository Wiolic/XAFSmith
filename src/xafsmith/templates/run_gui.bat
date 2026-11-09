@echo off
chcp 65001 >nul
rem 双击打开本项目的 XAFSmith 图形界面
cd /d "%~dp0"
set "XS=%LOCALAPPDATA%\XAFSmith\venv\Scripts\xafsmith.exe"
if exist ".venv\Scripts\xafsmith.exe" set "XS=.venv\Scripts\xafsmith.exe"
if not exist "%XS%" set "XS=xafsmith"
"%XS%" gui --project "%~dp0."
pause
