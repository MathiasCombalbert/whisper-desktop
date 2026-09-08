import os
import sys
import subprocess

# Si exécuté en tant que worker isolé pour la transcription Whisper
if "--worker" in sys.argv:
    # Retirer --worker pour ne pas perturber les modules
    from transcriber import run_worker
    run_worker()
    sys.exit(0)

# ==============================================================================
# 0. VERIFICATION IMMEDIATE D'INSTANCE UNIQUE (AVANT TOUT CHARGEMENT DE MODULE)
# ==============================================================================
MUTEX_NAME = "WhisperDesktop_SingleInstance_Mutex"
EVENT_NAME = "WhisperDesktop_Show_Event"
_single_instance_mutex = None
_single_instance_event = None
_lock_file_fd = None

if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    _single_instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        try:
            ev = kernel32.OpenEventW(0x0002, False, EVENT_NAME)  # EVENT_MODIFY_STATE
            if ev:
                kernel32.SetEvent(ev)
                kernel32.CloseHandle(ev)
        except Exception:
            pass
        sys.exit(0)
    _single_instance_event = kernel32.CreateEventW(None, False, False, EVENT_NAME)
else:
    ctypes = None
    try:
        import fcntl
        lock_path = os.path.expanduser("~/.whisperdesktop.lock")
        _lock_file_fd = open(lock_path, "w")
        fcntl.lockf(_lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        sys.exit(0)

# Bloquer PyTorch (inutile pour faster-whisper et consomme +400 Mo)
if "torch" not in sys.modules:
    sys.modules["torch"] = None

import json
import time
import threading
import datetime
import keyboard
import numpy as np

from audio_recorder import AudioRecorder
import paster
from bottom_bar import BottomBarHUD
from tray_app import SystemTrayManager
import autostart

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
    SRC_DIR = PROJECT_ROOT
else:
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SRC_DIR) if os.path.basename(SRC_DIR) == "src" else SRC_DIR

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

class WorkerTranscriberClient:
    """Gère le sous-processus Whisper isolé pour garantir 0 Mo de RAM résiduelle en arrière-plan."""
    def __init__(self, model_size="base", device="cuda", compute_type="float16"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.proc = None
        self._lock = threading.Lock()
        self.is_ready = False
        self.language = None
        self.initial_prompt = None

    def start(self):
        with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                return
            if getattr(sys, "frozen", False):
                exe = sys.executable
                cmd = [exe, "--worker", str(self.model_size), str(self.device), str(self.compute_type)]
            else:
                python_exe = sys.executable
                script = os.path.join(SRC_DIR, "app.py")
                cmd = [python_exe, script, "--worker", str(self.model_size), str(self.device), str(self.compute_type)]

            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                creationflags = 0x08000000 # CREATE_NO_WINDOW

            try:
                self.proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )

                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        break
                    line_clean = line.strip()
                    if "WD_READY" in line_clean or "READY" in line_clean:
                        self.is_ready = True
                        break
                    elif "WD_ERROR" in line_clean:
                        self.is_ready = False
                        log_event(f"[Worker Error] {line_clean}")
                        break
            except Exception as e:
                log_event(f"[Worker Error] Échec démarrage worker: {e}")
                self.is_ready = False

    def transcribe(self, audio_data: np.ndarray) -> str:
        with self._lock:
            if self.proc is None or self.proc.poll() is not None:
                self.start()
            if not self.is_ready or self.proc is None:
                return ""

            import tempfile
            temp_path = os.path.join(tempfile.gettempdir(), f"wd_audio_{os.getpid()}_{int(time.time()*1000)}.npy")
            np.save(temp_path, audio_data)

            req = json.dumps({
                "audio_path": temp_path,
                "language": self.language,
                "initial_prompt": self.initial_prompt
            })
            try:
                self.proc.stdin.write(req + "\n")
                self.proc.stdin.flush()
                while True:
                    resp_line = self.proc.stdout.readline()
                    if not resp_line:
                        return ""
                    resp_line = resp_line.strip()
                    if "status" in resp_line:
                        if resp_line.startswith("WD_RESP:"):
                            resp_line = resp_line[len("WD_RESP:"):]
                        resp = json.loads(resp_line)
                        if resp.get("status") == "ok":
                            return resp.get("text", "")
                        return ""
            except Exception as e:
                log_event(f"[Worker Error] Échec transcription: {e}")
            return ""

    def stop(self):
        with self._lock:
            if self.proc is not None:
                try:
                    self.proc.stdin.write("QUIT\n")
                    self.proc.stdin.flush()
                    self.proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
                self.proc = None
                self.is_ready = False

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.json")
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = os.path.join(SRC_DIR, "config.json")

LOG_FILE = os.path.join(PROJECT_ROOT, "app.log")

DEFAULT_CONFIG = {
    "hotkey": "alt+shift+v",
    "mode": "toggle",
    "model_size": "base",
    "device": "cuda",
    "compute_type": "float16",
    "language": None,
    "preserve_clipboard": False,
    "sound_feedback": False,
    "show_overlay": True,
    "auto_hide_seconds": 15,
    "idle_unload_seconds": 45,
    "audio_device": None,
    "start_with_windows": True,
    "initial_prompt": "Transcription en français pour le code, programmation, prompts, coller, copier, IA."
}

def log_event(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

class SpeechToTextApp:
    def __init__(self):
        log_event("Démarrage de SpeechToTextApp...")
        self.config = self.load_config()
        self.recorder = AudioRecorder(device=self.config.get("audio_device"))
        self.transcriber = None
        self.tray = None
        self.bottom_bar = None

        self.is_recording = False
        self.is_transcribing = False
        self.is_model_ready = False
        self.is_loading_model = False
        self.model_load_lock = threading.Lock()
        self.model_ready_event = threading.Event()
        self.idle_timer = None
        self.idle_lock = threading.Lock()
        self.last_work_hwnd = None
        self.hotkey_hook = None
        self._lock = threading.Lock()

        # Démarrer la surveillance continue de la fenêtre active de travail
        threading.Thread(target=self._track_foreground_loop, daemon=True).start()

        # Écouter les signaux d'activation en provenance d'autres instances (double-clic)
        threading.Thread(target=self._listen_single_instance_event, daemon=True).start()

        # Synchroniser l'autostart Windows au lancement si activé
        if self.config.get("start_with_windows", False):
            autostart.set_autostart(True)

    def _listen_single_instance_event(self):
        """Réveille la barre HUD si l'utilisateur double-clique à nouveau sur l'exécutable."""
        if sys.platform == "win32" and ctypes and _single_instance_event:
            kernel32 = ctypes.windll.kernel32
            while True:
                res = kernel32.WaitForSingleObject(_single_instance_event, 0xFFFFFFFF)
                if res == 0:  # WAIT_OBJECT_0
                    if self.bottom_bar and self.bottom_bar.root:
                        self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)

    def _track_foreground_loop(self):
        """
        Garde en mémoire en permanence la vraie fenêtre active de l'utilisateur.
        Filtre par PID sous Windows : ignore TOUTES les fenêtres appartenant à notre propre processus.
        """
        if sys.platform != "win32" or not ctypes:
            # Mode Linux / POSIX : suivi basé sur xdotool si disponible
            while True:
                time.sleep(0.1)
                try:
                    fg = paster.get_active_window()
                    if fg:
                        self.last_work_hwnd = fg
                except Exception:
                    pass
            return

        my_pid = os.getpid()
        user32 = ctypes.windll.user32
        while True:
            time.sleep(0.04)
            try:
                fg = paster.get_active_window()
                if fg and user32.IsWindow(fg):
                    win_pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(fg, ctypes.byref(win_pid))
                    if win_pid.value != my_pid and win_pid.value != 0:
                        self.last_work_hwnd = fg
            except Exception:
                pass

    @staticmethod
    def normalize_hotkey(hotkey_str: str) -> str:
        if not hotkey_str:
            return "alt+shift+v"
        raw_parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
        normalized_parts = []
        for p in raw_parts:
            if p in ("maj", "maj droite", "maj gauche", "left shift", "right shift"):
                p = "shift"
            elif p in ("control", "left ctrl", "right ctrl", "ctrl droite", "ctrl gauche", "strg", "strg droite", "strg gauche"):
                p = "ctrl"
            elif p in ("menu", "left alt", "right alt", "alt droite", "alt gauche", "alt gr", "altgr"):
                p = "alt"
            elif p in ("windows", "left windows", "right windows", "windows droite", "windows gauche", "super", "meta"):
                p = "win"
            if p not in normalized_parts:
                normalized_parts.append(p)

        # Si le raccourci a été tronqué accidentellement sur les modificateurs seuls (ex: alt+maj ou alt+shift suite au bug)
        if normalized_parts in (['alt', 'shift'], ['shift', 'alt'], ['alt'], ['shift'], ['ctrl']):
            return "alt+shift+v"

        return "+".join(normalized_parts) if normalized_parts else "alt+shift+v"

    def load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    res = {**DEFAULT_CONFIG, **cfg}
                    res["hotkey"] = self.normalize_hotkey(res.get("hotkey", "alt+shift+v"))
                    return res
            except Exception as e:
                log_event(f"Erreur lecture config: {e}")
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_event(f"Erreur sauvegarde config: {e}")

    def is_autostart_active(self) -> bool:
        return autostart.is_autostart_enabled()

    def set_autostart_active(self, enable: bool):
        self.config["start_with_windows"] = enable
        self.save_config()
        autostart.set_autostart(enable)

    def set_mode(self, mode: str):
        self.config["mode"] = mode
        self.save_config()
        log_event(f"Mode basculé sur: {mode}")

    def set_language(self, lang: str):
        self.config["language"] = None if lang == "auto" else lang
        self.save_config()
        if self.transcriber:
            self.transcriber.language = self.config["language"]
        log_event(f"Langue configurée sur: {lang}")

    def switch_microphone(self, device_index: int):
        self.config["audio_device"] = device_index
        self.save_config()
        self.recorder.switch_device(device_index)
        new_name = self.recorder.get_active_device_name()
        if self.bottom_bar:
            self.bottom_bar.set_mic_name(new_name)
        log_event(f"Microphone basculé sur : [{device_index}] {new_name}")

    def open_settings(self):
        from settings_dialog import SettingsDialog
        if self.bottom_bar and self.bottom_bar.root:
            self.bottom_bar.root.after(0, lambda: SettingsDialog(self.bottom_bar.root, self))

    def apply_settings(self, new_config: dict):
        log_event(f"Application des nouveaux paramètres : {new_config}")

        # 1. Microphone
        if "audio_device" in new_config and new_config["audio_device"] != self.config.get("audio_device"):
            self.switch_microphone(new_config["audio_device"])

        # 2. Raccourci
        old_hotkey = self.normalize_hotkey(self.config.get("hotkey", "alt+shift+v"))
        new_hotkey = self.normalize_hotkey(new_config.get("hotkey", old_hotkey))
        if new_hotkey != old_hotkey:
            self.config["hotkey"] = new_hotkey
            self.register_hotkey()

        # 3. Modèle Whisper
        old_model = self.config.get("model_size", "large-v3-turbo")
        new_model = new_config.get("model_size", old_model)
        if new_model != old_model:
            self.config["model_size"] = new_model
            threading.Thread(target=self._reload_whisper_thread, args=(new_model,), daemon=True).start()

        # 4. Langue
        self.config["language"] = new_config.get("language")
        if self.transcriber:
            self.transcriber.language = self.config["language"]

        # 5. Mode
        self.config["mode"] = new_config.get("mode", "toggle")

        # 6. Autostart
        if "start_with_windows" in new_config:
            self.set_autostart_active(new_config["start_with_windows"])

        self.save_config()

    def _ensure_model_loading(self):
        """Déclenche le chargement du modèle Whisper à la demande si pas encore prêt."""
        if self.is_model_ready and self.transcriber:
            return
        with self.model_load_lock:
            if not self.is_loading_model and (self.transcriber is None or not self.is_model_ready):
                self.is_loading_model = True
                self.model_ready_event.clear()
                threading.Thread(target=self._init_transcriber_async, daemon=True).start()

    def _reset_idle_timer(self):
        """Planifie le déchargement automatique du modèle après inactivité."""
        with self.idle_lock:
            if self.idle_timer:
                self.idle_timer.cancel()
            timeout = self.config.get("idle_unload_seconds", 45)
            if timeout and timeout > 0:
                self.idle_timer = threading.Timer(timeout, self.unload_transcriber)
                self.idle_timer.daemon = True
                self.idle_timer.start()

    def _cancel_idle_timer(self):
        """Annule le timer d'inactivité lorsqu'une dictée commence."""
        with self.idle_lock:
            if self.idle_timer:
                self.idle_timer.cancel()
                self.idle_timer = None

    def unload_transcriber(self):
        """Décharge complètement le modèle Whisper pour repasser en veille à mémoire quasi-nulle."""
        with self._lock:
            if self.is_recording or self.is_transcribing:
                # Ne pas décharger si une capture ou transcription est en cours
                self._reset_idle_timer()
                return

            if self.transcriber is not None:
                log_event("[Memory] Mise en veille : arrêt du worker Whisper...")
                try:
                    if hasattr(self.transcriber, "stop"):
                        self.transcriber.stop()
                    elif hasattr(self.transcriber, "model"):
                        del self.transcriber.model
                    del self.transcriber
                except Exception:
                    pass
                self.transcriber = None
                self.is_model_ready = False
                self.model_ready_event.clear()

                import gc
                gc.collect()
                if sys.platform == "win32":
                    try:
                        import ctypes
                        ctypes.windll.kernel32.SetProcessWorkingSetSize(
                            ctypes.windll.kernel32.GetCurrentProcess(),
                            ctypes.c_size_t(-1),
                            ctypes.c_size_t(-1)
                        )
                    except Exception:
                        pass
                log_event("[Memory] Worker Whisper arrêté. Mémoire libérée pour le mode veille (10-15 Mo).")
                if self.bottom_bar:
                    self.bottom_bar.show_ready_safe(status_msg="Prêt (veille)")
                if self.tray:
                    self.tray.set_state("standby")

    def _reload_whisper_thread(self, new_model_size: str):
        if self.transcriber is None:
            log_event(f"Nouveau modèle configuré : '{new_model_size}' (sera chargé à la prochaine invocation).")
            if self.bottom_bar and self.bottom_bar.root:
                self.bottom_bar.root.after(0, lambda: self.bottom_bar.preview_label.config(
                    text=f"Modèle '{new_model_size}' sélectionné !", fg="#a6e3a1"
                ))
            return

        if self.bottom_bar and self.bottom_bar.root:
            self.bottom_bar.root.after(0, lambda: self.bottom_bar.preview_label.config(
                text=f"Chargement du modèle '{new_model_size}'...", fg="#f9e2af"
            ))
        try:
            log_event(f"Rechargement du worker Whisper '{new_model_size}'...")
            self.unload_transcriber()
            self._ensure_model_loading()
            log_event(f"Worker Whisper '{new_model_size}' rechargé avec succès !")
            if self.bottom_bar and self.bottom_bar.root:
                self.bottom_bar.root.after(0, lambda: self.bottom_bar.preview_label.config(
                    text=f"Modèle '{new_model_size}' prêt !", fg="#a6e3a1"
                ))
            self._reset_idle_timer()
        except Exception as e:
            log_event(f"Erreur rechargement worker Whisper: {e}")

    def toggle_bar_visibility(self):
        if self.bottom_bar and self.bottom_bar.root:
            if self.bottom_bar.is_visible:
                self.bottom_bar.hide_to_tray()
            else:
                self.bottom_bar.restore_from_tray()

    def play_sound(self, sound_type: str):
        # 100% silencieux comme demandé
        pass

    def register_hotkey(self):
        raw_hotkey = self.config.get("hotkey", "alt+shift+v")
        hotkey_str = self.normalize_hotkey(raw_hotkey)
        self.config["hotkey"] = hotkey_str
        if self.hotkey_hook is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
            except Exception:
                pass
            self.hotkey_hook = None

        try:
            self.hotkey_hook = keyboard.add_hotkey(
                hotkey_str,
                self.on_hotkey_triggered,
                suppress=False
            )
            log_event(f"Raccourci global enregistré: '{hotkey_str.upper()}'")
        except Exception as e:
            log_event(f"Impossible d'enregistrer le raccourci '{hotkey_str}': {e}")

    def on_hotkey_triggered(self):
        try:
            current_hwnd = paster.get_active_window()
            threading.Thread(
                target=self._handle_hotkey_async,
                args=(current_hwnd,),
                daemon=True
            ).start()
        except Exception as e:
            log_event(f"[Hotkey Trigger Error] {e}")

    def _handle_hotkey_async(self, current_hwnd):
        self._cancel_idle_timer()

        if current_hwnd and (not self.bottom_bar or current_hwnd != self.bottom_bar.bar_hwnd):
            self.last_work_hwnd = current_hwnd

        mode = self.config.get("mode", "toggle")
        with self._lock:
            if self.is_transcribing:
                if self.bottom_bar:
                    self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)
                return

            if mode == "toggle":
                if not self.is_recording:
                    if self.bottom_bar:
                        self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)
                    self._ensure_model_loading()
                    self._start_recording()
                else:
                    self._stop_and_transcribe()
            elif mode == "push_to_talk":
                if not self.is_recording:
                    if self.bottom_bar:
                        self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)
                    self._ensure_model_loading()
                    self._start_recording()
                    threading.Thread(target=self._watch_key_release, daemon=True).start()

    def on_manual_action(self):
        """Déclenché par le clic sur le bouton de la barre HUD."""
        self._cancel_idle_timer()
        with self._lock:
            if self.is_transcribing:
                return
            if not self.is_recording:
                self._ensure_model_loading()
                self._start_recording()
            else:
                self._stop_and_transcribe()

    def _watch_key_release(self):
        hotkey_str = self.normalize_hotkey(self.config.get("hotkey", "alt+shift+v"))
        keys = [k.strip() for k in hotkey_str.split("+") if k.strip()]
        time.sleep(0.15)
        while self.is_recording and any(keyboard.is_pressed(k) for k in keys):
            time.sleep(0.04)

        with self._lock:
            if self.is_recording:
                self._stop_and_transcribe()

    def _start_recording(self):
        self.is_recording = True

        try:
            self.recorder.start()
        except Exception as e:
            log_event(f"Erreur démarrage micro: {e}")
            self.is_recording = False
            if self.bottom_bar:
                self.bottom_bar.show_loading_safe(f"Erreur micro: {e}")
            return

        if self.tray:
            self.tray.set_state("recording")

        if self.bottom_bar:
            self.bottom_bar.show_recording_safe()

        log_event("[Audio] Début de l'écoute...")

    def _stop_and_transcribe(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.is_transcribing = True

        if self.tray:
            self.tray.set_state("transcribing")

        if self.bottom_bar:
            self.bottom_bar.show_transcribing_safe()

        audio_data = self.recorder.stop()
        log_event(f"[Audio] Arrêt. {len(audio_data)} échantillons capturés (~{len(audio_data)/16000:.2f}s).")

        threading.Thread(
            target=self._process_transcription_worker,
            args=(audio_data, self.last_work_hwnd),
            daemon=True
        ).start()

    def _process_transcription_worker(self, audio_data, target_hwnd):
        last_text = ""
        try:
            # 1. Attendre que le modèle soit prêt s'il est en train de se charger à la demande
            if not self.is_model_ready or self.transcriber is None:
                if self.bottom_bar:
                    self.bottom_bar.show_loading_safe("Démarrage du modèle Whisper...")
                self._ensure_model_loading()
                ready = self.model_ready_event.wait(timeout=35)
                if not ready or self.transcriber is None:
                    raise RuntimeError("Le modèle Whisper n'a pas pu être chargé à temps.")

            if len(audio_data) < 3200:
                log_event("[Audio] Enregistrement trop court (< 0.2s).")
                last_text = ""
            else:
                start_t = time.time()
                text = self.transcriber.transcribe(audio_data)
                duration = time.time() - start_t
                last_text = text

                if text:
                    log_event(f"[Whisper ({duration:.2f}s)] Texte détecté : \"{text}\"")
                    dest_hwnd = target_hwnd if target_hwnd else self.last_work_hwnd
                    log_event(f"[Paster] Envoi du collage vers HWND: {dest_hwnd}")
                    paster.paste_text(text, target_hwnd=dest_hwnd, preserve_clipboard=False)
                    log_event("[Paster] Texte collé dans l'application cible.")
                else:
                    log_event(f"[Whisper ({duration:.2f}s)] Aucun texte audible détecté.")
        except Exception as e:
            log_event(f"[Process Error] {e}")
            if self.bottom_bar:
                self.bottom_bar.show_loading_safe(f"Erreur: {e}")
        finally:
            with self._lock:
                self.is_transcribing = False

            if self.tray:
                self.tray.set_state("ready")

            if self.bottom_bar:
                self.bottom_bar.show_ready_safe(last_text=last_text)

            # Lancer le compte à rebours pour décharger le modèle et repasser en veille
            self._reset_idle_timer()

    def stop_and_exit(self):
        log_event("Fermeture de l'application...")
        with self._lock:
            self.is_recording = False
            self.is_transcribing = False

        if self.hotkey_hook:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
            except Exception:
                pass

        if self.tray:
            self.tray.stop()

        if self.bottom_bar and self.bottom_bar.root:
            try:
                self.bottom_bar.root.quit()
                self.bottom_bar.root.destroy()
            except Exception:
                pass

        os._exit(0)

    def run(self):
        log_event("=" * 50)
        log_event("Initialisation de Speech-to-Text Whisper Desktop")

        # 1. Initialiser la Barre HUD IMMÉDIATEMENT (< 100ms)
        self.bottom_bar = BottomBarHUD(self)
        self.bottom_bar.create_window()

        mic_name = self.recorder.get_active_device_name()
        self.bottom_bar.set_mic_name(mic_name)
        log_event(f"Microphone configuré : {mic_name}")

        # 2. Initialiser le System Tray IMMÉDIATEMENT
        self.tray = SystemTrayManager(self)
        self.tray.start()
        self.tray.set_state("standby")

        # 3. Enregistrer le raccourci global
        self.register_hotkey()

        # Démarrage direct en veille (0 Mo de modèle chargé, ~35 Mo au total)
        self.bottom_bar.show_ready_safe(status_msg="Prêt (veille)")
        log_event("Application prête et en veille minimale (modèle chargé à la demande).")

        # 4. Boucle principale d'événements Tkinter
        try:
            self.bottom_bar.root.mainloop()
        except KeyboardInterrupt:
            self.stop_and_exit()

    def _init_transcriber_async(self):
        model_name = self.config.get("model_size", "base")
        try:
            log_event(f"[Memory] Démarrage du worker Whisper ({model_name}) à la demande...")
            client = WorkerTranscriberClient(
                model_size=model_name,
                device=self.config.get("device", "cuda"),
                compute_type=self.config.get("compute_type", "float16")
            )
            client.language = self.config.get("language")
            client.initial_prompt = self.config.get("initial_prompt")
            client.start()
            if not client.is_ready:
                raise RuntimeError("Le worker Whisper n'a pas pu démarrer.")
            self.transcriber = client
            self.is_model_ready = True
            self.is_loading_model = False
            self.model_ready_event.set()
            log_event(f"[Memory] Worker Whisper ({model_name}) prêt à l'emploi !")
            if self.bottom_bar:
                self.bottom_bar.show_ready_safe()
            if self.tray:
                self.tray.set_state("ready")
        except Exception as e:
            self.is_loading_model = False
            self.is_model_ready = False
            self.model_ready_event.set()
            log_event(f"[Erreur Init Worker] {e}")
            if self.bottom_bar:
                self.bottom_bar.show_loading_safe(f"Erreur modèle: {e}")

if __name__ == "__main__":
    try:
        app = SpeechToTextApp()
        app.run()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_event(f"FATAL ERROR: {tb}")
        for p in ["crash.log", os.path.join(PROJECT_ROOT, "crash.log")]:
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(tb)
            except Exception:
                pass
