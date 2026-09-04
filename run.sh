#!/usr/bin/env bash
cd "$(dirname "$0")"

# 1. Priorite au binaire autonome compile s'il existe
if [ -f "dist/WhisperDesktop/WhisperDesktop" ]; then
    nohup ./dist/WhisperDesktop/WhisperDesktop >/dev/null 2>&1 &
    echo "Whisper Desktop demarre en arriere-plan (PID: $!)."
    exit 0
fi

# 2. Sinon lancement via python3
if command -v python3 >/dev/null 2>&1; then
    nohup python3 src/app.py >/dev/null 2>&1 &
    echo "Whisper Desktop demarre en arriere-plan (PID: $!)."
    exit 0
fi

echo "[ERREUR] Aucun binaire compile trouve dans dist/WhisperDesktop/ ni d'interpreteur python3."
exit 1
