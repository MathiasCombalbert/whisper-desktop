import time
import ctypes
import pyperclip

# Constantes Win32 pour la simulation des touches
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32

def get_active_window():
    """Récupère le handle (HWND) de la fenêtre active au premier plan."""
    return user32.GetForegroundWindow()

def restore_active_window(hwnd):
    """Restaure le focus sur la fenêtre cible même si Windows tente de bloquer."""
    if not hwnd:
        return
    try:
        if not user32.IsWindow(hwnd):
            return
        cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        if cur_thread != target_thread:
            user32.AttachThreadInput(cur_thread, target_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.SetFocus(hwnd)
            user32.AttachThreadInput(cur_thread, target_thread, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
    except Exception as e:
        print(f"[Paster Warning] Restauration HWND {hwnd}: {e}")

def simulate_paste():
    """Simule la frappe Ctrl+V au niveau OS de manière propre sans Escape."""
    # 1. S'assurer que Alt, Shift et Ctrl sont physiquement relâchés
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.04)

    # 2. Appui sur Ctrl
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    # 3. Appui sur V
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.05)
    # 4. Relâche V
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    # 5. Relâche Ctrl
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

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
        # 1. Rétablir le focus sur la fenêtre cible (Antigravity)
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
