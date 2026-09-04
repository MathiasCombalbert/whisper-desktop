import os
import sys
import time
import shutil
import subprocess
import pyperclip

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12  # Alt
    VK_V = 0x56
    KEYEVENTF_KEYUP = 0x0002
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None

def get_active_window():
    """Récupère l'identifiant (HWND sous Windows, ID fenêtre sous Linux) de la fenêtre active."""
    if IS_WINDOWS and user32:
        try:
            return user32.GetForegroundWindow()
        except Exception:
            return None
    elif IS_LINUX:
        if shutil.which("xdotool"):
            try:
                out = subprocess.check_output(["xdotool", "getactivewindow"], stderr=subprocess.DEVNULL)
                return out.decode().strip()
            except Exception:
                pass
    return None

def restore_active_window(window_id):
    """Restaure le focus sur la fenêtre cible."""
    if not window_id:
        return

    if IS_WINDOWS and user32 and kernel32:
        try:
            if not user32.IsWindow(window_id):
                return
            cur_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(window_id, None)
            if cur_thread != target_thread:
                user32.AttachThreadInput(cur_thread, target_thread, True)
                user32.SetForegroundWindow(window_id)
                user32.BringWindowToTop(window_id)
                user32.SetFocus(window_id)
                user32.AttachThreadInput(cur_thread, target_thread, False)
            else:
                user32.SetForegroundWindow(window_id)
                user32.BringWindowToTop(window_id)
        except Exception as e:
            print(f"[Paster Warning] Restauration HWND {window_id}: {e}")
    elif IS_LINUX:
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "windowactivate", str(window_id)], check=False, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[Paster Warning] Restauration fenêtre Linux {window_id}: {e}")

def simulate_paste():
    """Simule la frappe Ctrl+V au niveau OS."""
    if IS_WINDOWS and user32:
        # 1. S'assurer que Alt, Shift et Ctrl sont physiquement relâchés
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)

        # 2. Appui sur Ctrl + V
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.05)
        # 3. Relâchement V puis Ctrl
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    else:
        # Linux : essai prioritaire avec xdotool
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=False, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
        # Fallback multiplateforme via pynput
        try:
            from pynput.keyboard import Controller, Key
            kb = Controller()
            time.sleep(0.05)
            with kb.pressed(Key.ctrl):
                kb.press('v')
                kb.release('v')
        except Exception as e:
            print(f"[Paster Warning] Simulation collage Linux: {e}")

def paste_text(text: str, target_hwnd=None, preserve_clipboard: bool = False):
    """
    Restaure la fenêtre active,
    copie le texte transcrit dans le presse-papier,
    et simule Ctrl+V dans l'application active.
    """
    if not text:
        return

    old_clipboard = None
    if preserve_clipboard:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = None

    try:
        # 1. Rétablir le focus sur la fenêtre cible
        if target_hwnd:
            restore_active_window(target_hwnd)
            time.sleep(0.08)

        # 2. Copier la transcription dans le presse-papier
        pyperclip.copy(text)
        time.sleep(0.05)

        # 3. Coller dans l'application active
        simulate_paste()

        # 4. Attendre avant de restaurer si preserve_clipboard est activé
        if preserve_clipboard and old_clipboard is not None:
            time.sleep(0.40)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
    except Exception as e:
        print(f"[Paster Error] Erreur lors du collage: {e}")
