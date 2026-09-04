import os
import sys

WINDOWS_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Whisper Desktop"

def get_startup_file_path() -> str:
    """Chemin pour Linux XDG autostart."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    return os.path.join(autostart_dir, "whisper-desktop.desktop")

def is_autostart_enabled() -> bool:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_REG_KEY, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except Exception:
            return False
    else:
        path = get_startup_file_path()
        return os.path.exists(path)

def set_autostart(enable: bool, root_dir: str = None):
    if not root_dir:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(src_dir) if os.path.basename(src_dir) == "src" else src_dir

    if sys.platform == "win32":
        import winreg

        # Nettoyer l'ancien script legacy VBScript du dossier Startup si présent
        legacy_vbs = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
            "SpeechToTextWhisper.vbs"
        )
        if os.path.exists(legacy_vbs):
            try:
                os.remove(legacy_vbs)
            except Exception:
                pass

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    if getattr(sys, "frozen", False):
                        cmd = f'"{sys.executable}"'
                    else:
                        exe_path = os.path.join(root_dir, "dist", "WhisperDesktop", "WhisperDesktop.exe")
                        if os.path.exists(exe_path):
                            cmd = f'"{exe_path}"'
                        else:
                            vbs_path = os.path.join(root_dir, "run_silent.vbs")
                            cmd = f'wscript.exe "{vbs_path}"'

                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                    print(f"[Autostart] Enregistré dans le Registre Windows (Gestionnaire des tâches) : {cmd}")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        print("[Autostart] Supprimé du Registre Windows.")
                    except FileNotFoundError:
                        pass
        except Exception as e:
            print(f"[Autostart Registry Error] {e}")

    else:
        # Linux : Fichier .desktop standard
        startup_file = get_startup_file_path()
        if enable:
            exec_path = os.path.join(root_dir, "dist", "WhisperDesktop", "WhisperDesktop")
            if not os.path.exists(exec_path):
                exec_path = os.path.join(root_dir, "run.sh")
            if not os.path.exists(exec_path):
                exec_path = f"{sys.executable} {os.path.join(root_dir, 'src', 'app.py')}"

            desktop_content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Whisper Desktop
Comment=Global Speech to Text Assistant
Exec={exec_path}
Terminal=false
Categories=Utility;AudioVideo;
X-GNOME-Autostart-enabled=true
"""
            os.makedirs(os.path.dirname(startup_file), exist_ok=True)
            with open(startup_file, "w", encoding="utf-8") as f:
                f.write(desktop_content)
            print(f"[Autostart] Démarrage automatique Linux activé : {startup_file}")
        else:
            if os.path.exists(startup_file):
                try:
                    os.remove(startup_file)
                    print(f"[Autostart] Démarrage automatique désactivé.")
                except Exception as e:
                    print(f"[Autostart Warning] Impossible de supprimer {startup_file}: {e}")
