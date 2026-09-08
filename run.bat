@echo off
cd /d "%~dp0"
if exist "%~dp0dist\WhisperDesktop\WhisperDesktop.exe" (
    start "" "%~dp0dist\WhisperDesktop\WhisperDesktop.exe"
) else (
    start "" wscript.exe scripts\run_silent.vbs
)
