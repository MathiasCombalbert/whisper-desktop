#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

show_menu() {
    clear 2>/dev/null || true
    echo "===================================================="
    echo "   Whisper Desktop - Setup & Build Manager (Linux)"
    echo "===================================================="
    echo ""
    echo "   [1] Installer les dependances (systeme + Python)"
    echo "   [2] Compiler le binaire Linux autonome (PyInstaller)"
    echo "   [3] Tout installer et compiler"
    echo "   [4] Quitter"
    echo ""
    echo "===================================================="
    read -rp "Choisissez une option [1-4] (defaut: 1) : " choice
    choice=${choice:-1}

    case "$choice" in
        1) install_deps ;;
        2) build_binary ;;
        3) build_all ;;
        4) exit 0 ;;
        *) echo "Choix invalide"; sleep 1; show_menu ;;
    esac
}

install_deps() {
    echo "===================================================="
    echo " [1/2] Dependances systeme requises"
    echo "===================================================="
    echo "Sur distributions basees sur Debian/Ubuntu :"
    echo "sudo apt-get install -y portaudio19-dev libasound2-dev libx11-dev xdotool python3-tk"
    echo ""
    if command -v apt-get >/dev/null 2>&1; then
        read -rp "Voulez-vous tenter l'installation automatique via apt ? (o/N) : " ans
        if [[ "$ans" =~ ^[oOyY]$ ]]; then
            sudo apt-get update && sudo apt-get install -y portaudio19-dev libasound2-dev libx11-dev xdotool python3-tk patchelf
        fi
    fi

    echo ""
    echo "===================================================="
    echo " [2/2] Dependances Python"
    echo "===================================================="
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements.txt
    echo ""
    echo "[SUCCES] Dependances installees avec succes !"
    read -rp "Appuyez sur Entree pour continuer..."
    show_menu
}

build_binary() {
    chmod +x build_linux.sh
    ./build_linux.sh
    read -rp "Appuyez sur Entree pour continuer..."
    show_menu
}

build_all() {
    install_deps
    build_binary
}

if [ "$1" = "--install" ]; then
    python3 -m pip install -r requirements.txt
    exit 0
fi

show_menu
