@echo off
cd /d "%~dp0"
echo ====================================================
echo  Whisper Desktop - Compilation Windows (PyInstaller)
echo ====================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH.
    pause
    exit /b 1
)

echo [1/4] Verification / Installation de PyInstaller...
python -m pip install --upgrade pyinstaller

echo.
echo [2/4] Compilation du binaire autonome Windows...
pyinstaller --noconsole --onedir --name "WhisperDesktop" ^
    --add-data "config.json;." ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --hidden-import "pystray" ^
    --hidden-import "sounddevice" ^
    --hidden-import "keyboard" ^
    --hidden-import "pyperclip" ^
    --hidden-import "pynput" ^
    src/app.py

if %errorlevel% neq 0 (
    echo [ERREUR] Echec de la compilation PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/4] Copie des fichiers annexes dans dist\WhisperDesktop\...
if exist "config.json" copy /y "config.json" "dist\WhisperDesktop\" >nul
if exist "run_debug.bat" copy /y "run_debug.bat" "dist\WhisperDesktop\" >nul
if exist "README.md" copy /y "README.md" "dist\WhisperDesktop\" >nul
if exist "LICENSE" copy /y "LICENSE" "dist\WhisperDesktop\" >nul

echo.
echo [4/4] Verification de l'executable genere...
if exist "dist\WhisperDesktop\WhisperDesktop.exe" (
    echo [SUCCES] Executable genere dans :
    echo   dist\WhisperDesktop\WhisperDesktop.exe
) else (
    echo [ERREUR] L'executable n'a pas pu etre trouve.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  Compilation Windows terminee avec succes !
echo ====================================================
