@echo off
cd /d "%~dp0"
if exist "WhisperDesktop.exe" (
    echo [Debug] Lancement de WhisperDesktop.exe...
    WhisperDesktop.exe
    pause
    goto end
)
cd /d "%~dp0.."
echo ====================================================
echo  Starting Whisper Desktop Speech-to-Text (Debug)
echo ====================================================

set APP_PATH=src\app.py
if not exist "%APP_PATH%" set APP_PATH=app.py

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%APP_PATH%"
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%APP_PATH%"
    goto end
)

if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" "%APP_PATH%"
    goto end
)

echo [ERROR] Python was not found in PATH.
pause

:end
