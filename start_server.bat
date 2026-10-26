@echo off
title Campus Lost and Found Server
echo ========================================================
echo   Campus Lost and Found System - Starting Application
echo ========================================================
cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Opening browser at http://localhost:5000 ...
start "" "http://localhost:5000"

echo Starting Flask server...
echo Press Ctrl+C in this window to stop the server anytime.
echo.
python app.py
pause
