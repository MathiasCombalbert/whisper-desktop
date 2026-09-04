import os
import sys
import json
import time
import threading
import datetime
import keyboard
import ctypes

from transcriber import init_cuda_dlls
init_cuda_dlls()

from audio_recorder import AudioRecorder
from transcriber import Transcriber
import paster
from bottom_bar import BottomBarHUD
from tray_app import SystemTrayManager
import autostart

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "app.log")

DEFAULT_CONFIG = {
    "hotkey": "alt+shift+v",
    "mode": "toggle",
    "model_size": "large-v3-turbo",
    "device": "cuda",
    "compute_type": "float16",
    "language": None,
    "preserve_clipboard": False,
    "sound_feedback": False,
    "show_overlay": True,
    "auto_hide_seconds": 15,
    "audio_device": None,
    "start_with_windows": False,
    "initial_prompt": "Transcription en français pour Antigravity, code, IA, programmation, prompts, coller, copier."
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
        self.last_work_hwnd = None
        self.hotkey_hook = None
        self._lock = threading.Lock()

        # Démarrer la surveillance continue de la fenêtre active de travail
        threading.Thread(target=self._track_foreground_loop, daemon=True).start()

        # Synchroniser l'autostart Windows au lancement si activé
        if self.config.get("start_with_windows", False):
            autostart.set_autostart(True)

    def _track_foreground_loop(self):
        """
        Garde en mémoire en permanence la vraie fenêtre active de l'utilisateur (Antigravity).
        Filtre par PID : ignore TOUTES les fenêtres appartenant à notre propre processus.
        """
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

    def load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return {**DEFAULT_CONFIG, **cfg}
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
        old_hotkey = self.config.get("hotkey", "alt+shift+v")
        new_hotkey = new_config.get("hotkey", old_hotkey).strip().lower()
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

    def _reload_whisper_thread(self, new_model_size: str):
        if self.bottom_bar and self.bottom_bar.root:
            self.bottom_bar.root.after(0, lambda: self.bottom_bar.preview_label.config(
                text=f"Chargement du modèle '{new_model_size}'...", fg="#f9e2af"
            ))
        try:
            log_event(f"Rechargement du modèle Whisper '{new_model_size}'...")
            self.transcriber.reload_model(model_size=new_model_size)
            log_event(f"Modèle Whisper '{new_model_size}' rechargé avec succès !")
            if self.bottom_bar and self.bottom_bar.root:
                self.bottom_bar.root.after(0, lambda: self.bottom_bar.preview_label.config(
                    text=f"Modèle '{new_model_size}' prêt !", fg="#a6e3a1"
                ))
        except Exception as e:
            log_event(f"Erreur rechargement modèle Whisper: {e}")

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
        hotkey_str = self.config.get("hotkey", "alt+shift+v").strip().lower()
        if self.hotkey_hook is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
            except Exception:
                pass
            self.hotkey_hook = None

        try:
            # suppress=True : Empêche Windows de propager 'Alt' à l'application cible
            self.hotkey_hook = keyboard.add_hotkey(
                hotkey_str,
                self.on_hotkey_triggered,
                suppress=True
            )
            log_event(f"Raccourci global enregistré: '{hotkey_str.upper()}' (suppress=True)")
        except Exception as e:
            try:
                self.hotkey_hook = keyboard.add_hotkey(
                    hotkey_str,
                    self.on_hotkey_triggered,
                    suppress=False
                )
                log_event(f"Raccourci global enregistré: '{hotkey_str.upper()}' (fallback)")
            except Exception as e2:
                log_event(f"Impossible d'enregistrer le raccourci: {e2}")

    def on_hotkey_triggered(self):
        current_hwnd = paster.get_active_window()
        threading.Thread(
            target=self._handle_hotkey_async,
            args=(current_hwnd,),
            daemon=True
        ).start()

    def _handle_hotkey_async(self, current_hwnd):
        if current_hwnd and (not self.bottom_bar or current_hwnd != self.bottom_bar.bar_hwnd):
            self.last_work_hwnd = current_hwnd

        mode = self.config.get("mode", "toggle")
        with self._lock:
            if self.is_transcribing:
                return

            if mode == "toggle":
                if not self.is_recording:
                    # Si la barre était masquée en arrière-plan, la faire apparaître immédiatement
                    if self.bottom_bar and not self.bottom_bar.is_visible:
                        self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)
                    self._start_recording()
                else:
                    self._stop_and_transcribe()
            elif mode == "push_to_talk":
                if not self.is_recording:
                    if self.bottom_bar and not self.bottom_bar.is_visible:
                        self.bottom_bar.root.after(0, self.bottom_bar.restore_from_tray)
                    self._start_recording()
                    threading.Thread(target=self._watch_key_release, daemon=True).start()

    def on_manual_action(self):
        """Déclenché par le clic sur le bouton de la barre HUD."""
        with self._lock:
            if self.is_transcribing:
                return
            if not self.is_recording:
                self._start_recording()
            else:
                self._stop_and_transcribe()

    def _watch_key_release(self):
        hotkey_str = self.config.get("hotkey", "alt+shift+v").strip().lower()
        keys = [k.strip() for k in hotkey_str.split("+")]
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
        finally:
            with self._lock:
                self.is_transcribing = False

            if self.tray:
                self.tray.set_state("ready")

            if self.bottom_bar:
                self.bottom_bar.show_ready_safe(last_text=last_text)

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

        # 1. Initialiser Whisper (large-v3-turbo sur GPU)
        self.transcriber = Transcriber(
            model_size=self.config.get("model_size", "large-v3-turbo"),
            device=self.config.get("device", "cuda"),
            compute_type=self.config.get("compute_type", "float16"),
            language=self.config.get("language"),
            initial_prompt=self.config.get("initial_prompt")
        )

        # 2. Initialiser la Barre HUD (démarrage masqué par défaut en arrière-plan)
        self.bottom_bar = BottomBarHUD(self)
        self.bottom_bar.create_window()

        mic_name = self.recorder.get_active_device_name()
        self.bottom_bar.set_mic_name(mic_name)
        log_event(f"Microphone configuré : {mic_name}")

        # 3. Initialiser le System Tray
        self.tray = SystemTrayManager(self)
        self.tray.start()

        # 4. Enregistrer le raccourci global
        self.register_hotkey()

        log_event("Application prête et en veille en arrière-plan !")

        # 5. Boucle principale d'événements Tkinter
        try:
            self.bottom_bar.root.mainloop()
        except KeyboardInterrupt:
            self.stop_and_exit()

if __name__ == "__main__":
    app = SpeechToTextApp()
    app.run()
