@echo off
cd /d "%~dp0"
title PPE Sentinel - 1-Click Dependency Installer for Team Laptops
echo ========================================================
echo   Setting up PPE Sentinel Dependencies for Demo
echo ========================================================
echo.

:: Check python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH!
    echo Please install Python 3.10 or 3.11 from python.org and check
    echo "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b
)

echo [1/2] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/2] Installing required project libraries (FastAPI, OpenCV, YOLOv8, PySerial)...
python -m pip install -r requirements.txt

echo.
echo ========================================================
echo   Setup Complete! All dependencies are installed.
echo   You can now plug in the Arduino and run START_WEBSITE.bat
echo ========================================================
echo.
pause

