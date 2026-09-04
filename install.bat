@echo off
cd /d "%~dp0"
echo ====================================================
echo  Whisper Desktop - Environment Setup
echo ====================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.10+ (64-bit) and ensure "Add Python to PATH" is checked.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version

echo [2/3] Upgrading pip...
python -m pip install --upgrade pip

echo [3/3] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt

echo.
echo ====================================================
echo  Installation completed successfully!
echo  You can now start the application:
echo   - Double-click 'run.bat' (runs silently in tray)
echo   - Or run 'run_debug.bat' (with console logs)
echo ====================================================
pause
