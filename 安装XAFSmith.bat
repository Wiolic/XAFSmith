@echo off
chcp 65001 >nul
rem 双击运行：打开 XAFSmith 安装向导（可选择安装位置、快捷方式等）
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0installer.py" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0installer.py" & exit /b 0)
where python >nul 2>nul && (python "%~dp0installer.py" & exit /b 0)
echo 没有找到 Python。请先安装 Python 3.11 或 3.12（安装时务必勾选 Add python.exe to PATH），
echo 装好后再双击本文件。正在打开下载页面 ...
start "" https://www.python.org/downloads/windows/
pause
