@echo off
cd /d "%~dp0"
echo ====================================================
echo  Whisper Desktop - Compilation Linux via Docker
echo ====================================================
echo.

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR] Docker n'est pas installe ou n'est pas dans votre PATH.
    echo Pour compiler pour Linux depuis Windows, Docker Desktop est requis.
    echo Telechargement : https://www.docker.com/products/docker-desktop/
    echo.
    echo Note : Les binaires Linux sont egalement compiles automatiquement
    echo sur GitHub Actions a chaque nouvelle version (Release).
    pause
    exit /b 1
)

docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR] Le moteur Docker n'est pas demarre.
    echo Veuillez lancer Docker Desktop puis relancer cette commande.
    echo.
    echo Note : Les binaires Linux sont egalement compiles automatiquement
    echo sur GitHub Actions a chaque nouvelle version (Release).
    pause
    exit /b 1
)

echo [1/3] Construction de l'image Docker Linux (Ubuntu + PyInstaller)...
docker build -t whisper-desktop-linux -f Dockerfile.linux .
if %errorlevel% neq 0 (
    echo [ERREUR] Echec de la construction de l'image Docker.
    pause
    exit /b 1
)

echo.
echo [2/3] Extraction de l'archive Linux compilee...
if not exist "dist\linux" mkdir "dist\linux"
docker run --rm -v "%cd%\dist\linux:/output" whisper-desktop-linux
if %errorlevel% neq 0 (
    echo [ERREUR] Echec de l'extraction de l'archive.
    pause
    exit /b 1
)

echo.
echo [3/3] Verification de l'archive generee...
if exist "dist\linux\WhisperDesktop-Linux-x64.tar.gz" (
    echo [SUCCES] L'archive Linux a ete generee dans :
    echo   dist\linux\WhisperDesktop-Linux-x64.tar.gz
) else (
    echo [AVERTISSEMENT] Verifiez le contenu du dossier dist\linux\
)

echo.
echo ====================================================
echo  Compilation Linux terminee !
echo ====================================================
pause
