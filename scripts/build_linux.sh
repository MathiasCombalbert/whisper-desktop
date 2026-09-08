#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "===================================================="
echo " Whisper Desktop - Linux Build (x86_64)"
echo "===================================================="

# Verification des dependances systeme de base
echo "[1/4] Verification de Python..."
python3 --version

echo "[2/4] Installation / Mise a jour des dependances..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "[3/4] Compilation avec PyInstaller..."
pyinstaller --noconsole --onedir --noconfirm --name "WhisperDesktop" \
    --add-data "config.json:." \
    --collect-all faster_whisper \
    --collect-all ctranslate2 \
    --hidden-import "pystray" \
    --hidden-import "sounddevice" \
    --hidden-import "keyboard" \
    --hidden-import "pyperclip" \
    --hidden-import "pynput" \
    src/app.py

echo "[4/4] Finalisation du package..."
cp config.json dist/WhisperDesktop/
cp README.md dist/WhisperDesktop/
cp LICENSE dist/WhisperDesktop/
chmod +x dist/WhisperDesktop/WhisperDesktop

cd dist
tar -czvf WhisperDesktop-Linux-x64.tar.gz WhisperDesktop/

echo "===================================================="
echo " Compilation Linux terminee avec succes !"
echo " Archive generee : dist/WhisperDesktop-Linux-x64.tar.gz"
echo " Dossier binaire : dist/WhisperDesktop/"
echo "===================================================="
