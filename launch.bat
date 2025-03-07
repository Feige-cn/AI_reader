@echo off
setlocal

::  清理可能存在的旧进程
taskkill /f /im python.exe >nul 2>&1

:: 切换到批处理文件所在目录（项目根目录）
cd /d %~dp0

:: 设置venv的Python路径（相对于批处理文件的位置）
set VENV_PYTHON=%~dp0venv\python.exe

:: 检查python.exe是否存在
if not exist "%VENV_PYTHON%" (
    echo 错误：未找到虚拟环境的 Python 可执行文件。
    echo 请确保 venv 已正确创建，并且路径为：%VENV_PYTHON%
    pause
    exit /b 1
)

echo 正在启动服务端...
"%VENV_PYTHON%" "%~dp0api_server.py"

endlocal
pause