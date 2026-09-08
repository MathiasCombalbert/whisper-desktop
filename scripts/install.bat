@echo off
cd /d "%~dp0.."
title Whisper Desktop - Setup & Build Manager

:menu
cls
echo ====================================================
echo   Whisper Desktop - Setup & Build Manager
echo ====================================================
echo.
echo   [1] Installer les dependances Python locales
echo   [2] Compiler l'executable Windows (PyInstaller .exe)
echo   [3] Compiler pour Linux via Docker (archive .tar.gz)
echo   [4] Tout installer et compiler (Windows + Linux)
echo   [5] Quitter
echo.
echo ====================================================
set /p choice="Choisissez une option [1-5] (defaut: 1) : "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto install_deps
if "%choice%"=="2" goto build_windows
if "%choice%"=="3" goto build_linux
if "%choice%"=="4" goto build_all
if "%choice%"=="5" goto exit_script

echo [ERREUR] Choix invalide. Veuillez reessayer.
timeout /t 2 >nul
goto menu

:install_deps
cls
echo ====================================================
echo  [1/1] Installation des dependances Python...
echo ====================================================
echo.
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'a pas ete trouve dans le PATH.
    echo Veuillez installer Python 3.10+ (64-bit) et cocher "Add Python to PATH".
    echo Telechargement : https://www.python.org/downloads/
    pause
    goto menu
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo [SUCCES] Dependances installees avec succes !
pause
goto menu

:build_windows
cls
call "%~dp0build_windows.bat"
pause
goto menu

:build_linux
cls
call "%~dp0build_linux.bat"
goto menu

:build_all
cls
echo ====================================================
echo  Compilation complete (Windows + Linux)
echo ====================================================
echo.
echo --- Etape 1 : Dependances ---
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo --- Etape 2 : Compilation Windows ---
call "%~dp0build_windows.bat"
echo.
echo --- Etape 3 : Compilation Linux (Docker) ---
call "%~dp0build_linux.bat"
echo.
echo [SUCCES] Processus termine.
pause
goto menu

:exit_script
echo Au revoir.
exit /b 0
