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
set "RPFM_ARGS=--no-rpfm"
if exist "work\rpfm-dist\rpfm_server.exe" set "RPFM_ARGS="
if exist "work\rpfm-master\target\debug\rpfm_server.exe" set "RPFM_ARGS="
if exist "work\rpfm-master\target\debug\rpfm_server" set "RPFM_ARGS="

if "%RPFM_ARGS%"=="--no-rpfm" if exist "work\rpfm-master\Cargo.toml" (
    echo RPFM source found, but rpfm_server.exe is missing.
    echo Building RPFM server...
    echo.
    powershell -ExecutionPolicy Bypass -File scripts\build_rpfm_server.ps1
    if errorlevel 1 (
        echo.
        echo RPFM server build failed. Install Visual Studio Build Tools with Desktop development with C++, then run this launcher again.
        echo.
        pause
        exit /b 1
    )
    if exist "work\rpfm-master\target\debug\rpfm_server.exe" set "RPFM_ARGS="
)

"%PYTHON_EXE%" scripts\dev_server.py %RPFM_ARGS% --open-browser

echo.
echo Server stopped.
pause
