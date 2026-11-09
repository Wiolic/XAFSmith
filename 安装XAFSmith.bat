@echo off
chcp 65001 >nul
title 安装 XAFSmith
setlocal
set "VENV=%LOCALAPPDATA%\XAFSmith\venv"
set "SRC=%~dp0"
echo ============================================
echo   XAFSmith 一键安装（约 5-10 分钟，需要联网）
echo ============================================
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
echo [1/3] 创建独立的 Python 环境：%VENV%
%PY% -m venv "%VENV%"
if errorlevel 1 goto fail
echo [2/3] 安装 XAFSmith 及其依赖 ...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install "%SRC%."
if errorlevel 1 goto fail
echo [3/3] 在桌面创建快捷方式 XAFSmith
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'XAFSmith.lnk')); $s.TargetPath=(Join-Path $env:SRC '启动XAFSmith.bat'); $s.WorkingDirectory=$env:SRC; $s.Save()"
echo.
echo 安装完成！以后双击桌面上的 XAFSmith 即可打开软件。
pause
exit /b 0

:nopython
echo 没有找到 Python。请先安装 Python 3.11 或 3.12（安装时务必勾选 Add python.exe to PATH），
echo 装好后再双击本文件。正在打开下载页面 ...
start "" https://www.python.org/downloads/windows/
pause
exit /b 1

:fail
echo 安装失败。请把这个窗口的内容截图发给维护者。
pause
exit /b 1
