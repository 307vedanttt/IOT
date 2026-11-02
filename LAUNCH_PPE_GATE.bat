@echo off
cd /d "%~dp0"
title PPE Compliance Gate - Mission Control
echo ========================================================
echo   Launching PPE Compliance Gate Mission Control...
echo ========================================================
echo 1. Auto-detecting Arduino on USB...
echo 2. Loading YOLOv8 Edge Vision AI...
echo 3. Starting Web Server on http://127.0.0.1:8000
echo.

start "" "http://127.0.0.1:8000"
"C:\Users\Vedant\AppData\Local\Programs\Python\Python311\python.exe" app.py
if %errorlevel% neq 0 (
    echo.
    echo Server stopped with error code %errorlevel%.
    pause
)

