@echo off
setlocal

::  ������ܴ��ڵľɽ���
taskkill /f /im python.exe >nul 2>&1

:: �л����������ļ�����Ŀ¼����Ŀ��Ŀ¼��
cd /d %~dp0

:: ����venv��Python·����������������ļ���λ�ã�
set VENV_PYTHON=%~dp0venv\python.exe

:: ���python.exe�Ƿ����
if not exist "%VENV_PYTHON%" (
    echo ����δ�ҵ����⻷���� Python ��ִ���ļ���
    echo ��ȷ�� venv ����ȷ����������·��Ϊ��%VENV_PYTHON%
    pause
    exit /b 1
)

echo �������������...
"%VENV_PYTHON%" "%~dp0api_server.py"

endlocal
pause