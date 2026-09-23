@echo off
setlocal

cd /d "%~dp0"
title LocalTTS

echo ========================================================
echo               Launching LocalTTS v3.1
echo ========================================================
echo.

set "PY_EXE="

:: 1. Check if uv-installed Python 3.12 exists
if exist "%APPDATA%\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" (
    set "PY_EXE=%APPDATA%\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
)

:: 2. Fallback to py launcher (try 64-bit 3.12 or default)
if "%PY_EXE%"=="" (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=py"
    )
)

:: 3. Fallback to system python.exe
if "%PY_EXE%"=="" (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
    )
)

:: If no python found, report error
if "%PY_EXE%"=="" (
    echo [ERROR] No Python interpreter found!
    echo Please install Python 3.10 - 3.12 from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Using Python: %PY_EXE%
echo Starting main.py...
echo.

"%PY_EXE%" main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [Application exited with code %ERRORLEVEL%]
    pause
)
