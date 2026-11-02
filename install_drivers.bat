@echo off
setlocal

:: Check for administrative privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: Set working directory to this script's folder
cd /d "%~dp0"

echo ========================================================
echo   Installing FTDI USB and Virtual COM Port Drivers
echo ========================================================
echo.

echo Installing ftdibus.inf...
pnputil /add-driver "%~dp0ftdi_drivers\ftdibus.inf" /install
echo.

echo Installing ftdiport.inf...
pnputil /add-driver "%~dp0ftdi_drivers\ftdiport.inf" /install
echo.

echo ========================================================
echo Driver installation finished!
echo Please unplug the Arduino USB cable and plug it back in.
echo ========================================================
pause
