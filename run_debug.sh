#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "===================================================="
echo " Whisper Desktop - Lancement Mode Debug (Linux)"
echo "===================================================="

if [ -f "dist/WhisperDesktop/WhisperDesktop" ]; then
    echo "Lancement du binaire compile..."
    ./dist/WhisperDesktop/WhisperDesktop
else
    echo "Lancement direct via Python..."
    python3 src/app.py
fi
