@echo off
cd /d "%~dp0"
echo ====================================================
echo  Starting Whisper Desktop Speech-to-Text (Debug)
echo ====================================================

where python >nul 2>nul
if %errorlevel% equ 0 (
    python app.py
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py app.py
    goto end
)

if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" app.py
    goto end
)

echo [ERROR] Python was not found in PATH.
echo Please install Python 3.10+ from python.org or add it to your PATH.
pause

:end
