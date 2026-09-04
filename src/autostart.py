import os
import sys

def get_startup_file_path() -> str:
    if sys.platform == "win32":
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        return os.path.join(startup_dir, "SpeechToTextWhisper.vbs")
    else:
        # Standard XDG Autostart pour Linux
        autostart_dir = os.path.expanduser("~/.config/autostart")
        return os.path.join(autostart_dir, "whisper-desktop.desktop")

def is_autostart_enabled() -> bool:
    path = get_startup_file_path()
    return os.path.exists(path)

def set_autostart(enable: bool, root_dir: str = None):
    startup_file = get_startup_file_path()
    if enable:
        if not root_dir:
            src_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(src_dir) if os.path.basename(src_dir) == "src" else src_dir
        
        if sys.platform == "win32":
            python_exe = sys.executable
            pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = python_exe

            # Script VBScript qui détecte le binaire compilé ou le lanceur Python
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strRoot = "{root_dir}"
WshShell.CurrentDirectory = strRoot

strExe = strRoot & "\\dist\\WhisperDesktop\\WhisperDesktop.exe"
If FSO.FileExists(strExe) Then
    WshShell.Run """" & strExe & """", 0, False
ElseIf FSO.FileExists(strRoot & "\\run_silent.vbs") Then
    WshShell.Run "wscript.exe """ & strRoot & "\\run_silent.vbs""", 0, False
Else
    WshShell.Run """" & "{pythonw_exe}" & """ """ & strRoot & "\\src\\app.py""", 0, False
End If
'''
            os.makedirs(os.path.dirname(startup_file), exist_ok=True)
            with open(startup_file, "w", encoding="utf-8") as f:
                f.write(vbs_content)
            print(f"[Autostart] Démarrage automatique Windows activé : {startup_file}")
        else:
            # Linux : Fichier .desktop standard
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
