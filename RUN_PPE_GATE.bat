@echo off
cd /d "%~dp0"
title PPE Compliance Gate - Camera & AI Detection
echo ========================================================
echo   Starting PPE Compliance Gate Controller
echo ========================================================
echo Connecting to Arduino...
echo Loading YOLOv8 PPE model (best.pt)...
echo.

:: 1. Check if 'python' is directly in PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    python main.py
    goto :DONE
)

:: 2. Check if Python 'py' launcher is installed
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 main.py
    goto :DONE
)

:: 3. Check LocalAppData
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py
    goto :DONE
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" main.py
    goto :DONE
)

python main.py

:DONE
if %errorlevel% neq 0 (
    echo.
    echo Program exited with an error. Check details above.
    pause
)
