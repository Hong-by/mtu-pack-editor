@echo off
setlocal

cd /d "%~dp0"
title MTU Pack Editor

echo MTU Pack Editor
echo Starting local server...
echo.

set "PYTHON_EXE="
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PYTHON%" (
    set "PYTHON_EXE=%BUNDLED_PYTHON%"
    goto :python_found
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    goto :python_found
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto :python_found
)

where python3 >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python3"
    goto :python_found
)

echo Python was not found.
echo Install Python 3.11+ from https://www.python.org/downloads/ or run this from Codex where the bundled Python exists.
echo.
pause
exit /b 1

:python_found
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%PYTHON_EXE%' 'scripts\dev_server.py' --open-browser"

echo.
echo Server stopped.
pause
