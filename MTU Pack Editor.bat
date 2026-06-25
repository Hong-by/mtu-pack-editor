@echo off
setlocal

cd /d "%~dp0"
title MTU Pack Editor

echo MTU Pack Editor
echo Starting local server...
echo.

set "PYTHON_EXE="
set "PORTABLE_PYTHON=%~dp0runtime\python\python.exe"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%PORTABLE_PYTHON%" (
    set "PYTHON_EXE=%PORTABLE_PYTHON%"
    goto :python_found
)

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
echo This package should include runtime\python\python.exe.
echo If you downloaded Source code instead of the portable release zip, download the Windows portable zip from the release page.
echo For development builds, install Python 3.11+ from https://www.python.org/downloads/.
echo.
pause
exit /b 1

:python_found
set "RPFM_ARGS=--no-rpfm"
if exist "work\rpfm-dist\rpfm_server.exe" set "RPFM_ARGS="
if exist "work\rpfm-master\target\debug\rpfm_server.exe" set "RPFM_ARGS="
if exist "work\rpfm-master\target\debug\rpfm_server" set "RPFM_ARGS="

if "%RPFM_ARGS%"=="--no-rpfm" (
    echo RPFM server was not found.
    echo This package should include work\rpfm-dist\rpfm_server.exe.
    echo If you downloaded Source code instead of the portable release zip, download the Windows portable zip from the release page.
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" scripts\dev_server.py %RPFM_ARGS% --open-browser

echo.
echo Server stopped.
pause
