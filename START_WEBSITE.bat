@echo off
cd /d "%~dp0"
title PPE Sentinel - Autonomous Safety Gate Server
echo ========================================================
echo   Starting PPE Sentinel SCADA Web Control Server
echo ========================================================
echo Web Dashboard URL: http://127.0.0.1:8000
echo.

:: 1. Check if 'python' is directly in PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] Using Python from system PATH
    python app.py
    goto :DONE
)

:: 2. Check if Python 'py' launcher is installed
where py >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] Using Python launcher (py -3)
    py -3 app.py
    goto :DONE
)

:: 3. Check typical user AppData Python installations (Python 3.11, 3.10, 3.12)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    echo [OK] Using Python 3.11 from LocalAppData
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" app.py
    goto :DONE
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    echo [OK] Using Python 3.10 from LocalAppData
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" app.py
    goto :DONE
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    echo [OK] Using Python 3.12 from LocalAppData
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" app.py
    goto :DONE
)

:: 4. Fallback attempt
echo [INFO] Attempting default 'python' command...
python app.py

:DONE
if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo   Server encountered an error or stopped.
    echo   Make sure dependencies are installed:
    echo   Run SETUP_NEW_LAPTOP.bat first.
    echo ========================================================
    pause
)
