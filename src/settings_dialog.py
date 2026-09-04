import tkinter as tk
from tkinter import ttk
import keyboard

MODELS = [
    ("large-v3-turbo", "large-v3-turbo (Recommandé - Ultra rapide & Haute précision, RTX)"),
    ("medium", "medium (Haute précision)"),
    ("small", "small (Léger & Rapide)"),
    ("base", "base (Très léger)"),
    ("tiny", "tiny (Ultra minimal)"),
]

LANGUAGES = [
    (None, "Automatique (Détection multilingue)"),
    ("fr", "Français (fr)"),
    ("en", "Anglais (en)"),
    ("es", "Espagnol (es)"),
    ("de", "Allemand (de)"),
    ("it", "Italien (it)"),
]

MODES = [
    ("toggle", "Basculer (Appuyer pour parler, réappuyer pour coller)"),
    ("push_to_talk", "Maintenir pour parler (Push-to-Talk)"),
]

class HotkeyRecorder:
    """Enregistreur d'événements clavier interactif pour assigner un raccourci style jeu vidéo."""
    MOD_MAP = {
        'ctrl': 'ctrl', 'control': 'ctrl', 'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
        'alt': 'alt', 'menu': 'alt', 'left alt': 'alt', 'right alt': 'alt',
        'shift': 'shift', 'left shift': 'shift', 'right shift': 'shift',
        'windows': 'win', 'left windows': 'win', 'right windows': 'win'
    }

    def __init__(self, on_done, on_cancel):
        self.on_done = on_done
        self.on_cancel = on_cancel
        self.hook = None
        self.modifiers = set()
        self.is_recording = False

    def start(self):
        self.is_recording = True
        self.modifiers.clear()
        self.hook = keyboard.hook(self._handler, suppress=False)

    def stop(self):
        self.is_recording = False
        if self.hook:
            try:
                keyboard.unhook(self.hook)
            except Exception:
                pass
            self.hook = None

    def _handler(self, e):
        if not self.is_recording:
            return

        name = e.name.lower()
        mod = self.MOD_MAP.get(name)

        if e.event_type == keyboard.KEY_DOWN:
            if name in ('esc', 'escape'):
                self.stop()
                self.on_cancel()
                return

            if mod:
                self.modifiers.add(mod)
            else:
                # Touche principale pressée
                parts = []
                for m in ['ctrl', 'alt', 'shift', 'win']:
                    if m in self.modifiers:
                        parts.append(m)
                parts.append(name)
                hotkey = '+'.join(parts)
                self.stop()
                self.on_done(hotkey)

        elif e.event_type == keyboard.KEY_UP:
            if mod in self.modifiers:
                self.modifiers.discard(mod)


class SettingsDialog:
    def __init__(self, parent, app_controller):
        self.parent = parent
        self.app = app_controller
        self.config = app_controller.config.copy()
        self.current_hotkey = self.config.get("hotkey", "alt+shift+v").strip().lower()

        self.hotkey_recorder = HotkeyRecorder(
            on_done=self._on_hotkey_captured,
            on_cancel=self._on_hotkey_cancelled
        )
        
        self.win = tk.Toplevel(parent)
        self.win.title("Paramètres Speech-to-Text")
        self.win.configure(bg="#181825")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)

        # Centrage de la fenêtre
        w, h = 520, 580
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # Thème TTK sombre pour comboboxes
        self._setup_styles()

        # Construction du formulaire
        self._build_ui()

        # Focus modal
        self.win.transient(parent)
        self.win.grab_set()

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(
            "Dark.TCombobox",
            fieldbackground="#313244",
            background="#45475a",
            foreground="#cdd6f4",
            darkcolor="#181825",
            lightcolor="#313244",
            bordercolor="#313244",
            arrowcolor="#89b4fa"
        )
        self.style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", "#313244")],
            selectbackground=[("readonly", "#45475a")],
            selectforeground=[("readonly", "#cdd6f4")]
        )

    def _format_hotkey_display(self, hk: str) -> str:
        parts = [p.capitalize() for p in hk.split("+")]
        return " + ".join(parts)

    def _build_ui(self):
        container = tk.Frame(self.win, bg="#181825", padx=24, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        # En-tête
        header_frame = tk.Frame(container, bg="#181825")
        header_frame.pack(fill=tk.X, pady=(0, 16))

        title_label = tk.Label(
            header_frame,
            text="Paramètres de Dictée Vocale",
            font=("Segoe UI", 13, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        )
        title_label.pack(anchor="w")

        sub_label = tk.Label(
            header_frame,
            text="Configurez votre matériel, modèle d'IA et raccourcis.",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        )
        sub_label.pack(anchor="w", pady=(2, 0))

        # --- 1. Microphone ---
        mic_frame = tk.Frame(container, bg="#181825")
        mic_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            mic_frame,
            text="Microphone d'entrée :",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        self.devices = self.app.recorder.get_available_devices()
        dev_names = [f"{d['name']} ({d['api']})" for d in self.devices]
        if not dev_names:
            dev_names = ["Microphone par défaut Windows"]

        self.mic_combo = ttk.Combobox(
            mic_frame,
            values=dev_names,
            state="readonly",
            style="Dark.TCombobox",
            font=("Segoe UI", 9)
        )
        self.mic_combo.pack(fill=tk.X)

        cur_idx = self.app.recorder.active_device_index
        selected_combo_idx = 0
        for i, d in enumerate(self.devices):
            if d["index"] == cur_idx:
                selected_combo_idx = i
                break
        if dev_names:
            self.mic_combo.current(selected_combo_idx)

        # --- 2. Modèle Whisper ---
        model_frame = tk.Frame(container, bg="#181825")
        model_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            model_frame,
            text="Modèle d'IA Whisper :",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        model_labels = [label for _, label in MODELS]
        self.model_combo = ttk.Combobox(
            model_frame,
            values=model_labels,
            state="readonly",
            style="Dark.TCombobox",
            font=("Segoe UI", 9)
        )
        self.model_combo.pack(fill=tk.X)

        cur_model = self.config.get("model_size", "large-v3-turbo")
        cur_model_idx = 0
        for i, (m_val, _) in enumerate(MODELS):
            if m_val == cur_model:
                cur_model_idx = i
                break
        self.model_combo.current(cur_model_idx)

        tk.Label(
            model_frame,
            text="large-v3-turbo offre la meilleure vitesse GPU (~0.5s) et précision.",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#181825"
        ).pack(anchor="w", pady=(2, 0))

        # --- 3. Langue ---
        lang_frame = tk.Frame(container, bg="#181825")
        lang_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            lang_frame,
            text="Langue de transcription :",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        lang_labels = [label for _, label in LANGUAGES]
        self.lang_combo = ttk.Combobox(
            lang_frame,
            values=lang_labels,
            state="readonly",
            style="Dark.TCombobox",
            font=("Segoe UI", 9)
        )
        self.lang_combo.pack(fill=tk.X)

        cur_lang = self.config.get("language")
        cur_lang_idx = 0
        for i, (l_val, _) in enumerate(LANGUAGES):
            if l_val == cur_lang or (l_val is None and cur_lang in [None, "auto"]):
                cur_lang_idx = i
                break
        self.lang_combo.current(cur_lang_idx)

        # --- 4. Raccourci Clavier Interactif (Style Gaming) ---
        hk_frame = tk.Frame(container, bg="#181825")
        hk_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            hk_frame,
            text="Raccourci clavier global :",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        hk_row = tk.Frame(hk_frame, bg="#181825")
        hk_row.pack(fill=tk.X)

        self.hk_btn = tk.Button(
            hk_row,
            text=self._format_hotkey_display(self.current_hotkey),
            font=("Segoe UI", 10, "bold"),
            bg="#313244",
            fg="#89b4fa",
            activebackground="#45475a",
            activeforeground="#b4befe",
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._start_hotkey_capture
        )
        self.hk_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        reset_btn = tk.Button(
            hk_row,
            text="↺ Défaut",
            font=("Segoe UI", 8),
            bg="#1e1e2e",
            fg="#6c7086",
            activebackground="#313244",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._reset_default_hotkey
        )
        reset_btn.pack(side=tk.RIGHT)

        self.hk_help_label = tk.Label(
            hk_frame,
            text="Cliquez sur le bouton pour assigner une touche (ex: Alt+W, F8, Ctrl+Shift+Space...).",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#181825"
        )
        self.hk_help_label.pack(anchor="w", pady=(3, 0))

        # --- 5. Mode de déclenchement ---
        mode_frame = tk.Frame(container, bg="#181825")
        mode_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            mode_frame,
            text="Comportement du raccourci :",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        mode_labels = [label for _, label in MODES]
        self.mode_combo = ttk.Combobox(
            mode_frame,
            values=mode_labels,
            state="readonly",
            style="Dark.TCombobox",
            font=("Segoe UI", 9)
        )
        self.mode_combo.pack(fill=tk.X)

        cur_mode = self.config.get("mode", "toggle")
        cur_mode_idx = 0
        for i, (m_val, _) in enumerate(MODES):
            if m_val == cur_mode:
                cur_mode_idx = i
                break
        self.mode_combo.current(cur_mode_idx)

        # --- 6. Démarrage avec Windows & Options ---
        opt_frame = tk.Frame(container, bg="#181825")
        opt_frame.pack(fill=tk.X, pady=(0, 16))

        self.autostart_var = tk.BooleanVar(value=self.app.is_autostart_active())
        self.autostart_cb = tk.Checkbutton(
            opt_frame,
            text="Lancer automatiquement au démarrage de Windows",
            variable=self.autostart_var,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#181825",
            selectcolor="#313244",
            activebackground="#181825",
            activeforeground="#cdd6f4"
        )
        self.autostart_cb.pack(anchor="w")

        # --- Boutons Enregistrer / Annuler ---
        btn_frame = tk.Frame(container, bg="#181825")
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        save_btn = tk.Button(
            btn_frame,
            text="Enregistrer les modifications",
            font=("Segoe UI", 9, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            activeforeground="#11111b",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._on_save
        )
        save_btn.pack(side=tk.RIGHT, padx=(6, 0))

        cancel_btn = tk.Button(
            btn_frame,
            text="Annuler",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#a6adc8",
            activebackground="#45475a",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._on_close
        )
        cancel_btn.pack(side=tk.RIGHT)

    def _start_hotkey_capture(self):
        self.hk_btn.config(
            text="Appuyez sur vos touches... (Échap pour annuler)",
            bg="#f9e2af",
            fg="#11111b"
        )
        self.hk_help_label.config(
            text="Écoute active en cours... Appuyez sur votre combinaison de touches.",
            fg="#f9e2af"
        )
        self.hotkey_recorder.start()

    def _on_hotkey_captured(self, new_hotkey: str):
        self.current_hotkey = new_hotkey
        self.win.after(0, self._finish_capture_ui)

    def _on_hotkey_cancelled(self):
        self.win.after(0, self._finish_capture_ui)

    def _finish_capture_ui(self):
        self.hk_btn.config(
            text=self._format_hotkey_display(self.current_hotkey),
            bg="#313244",
            fg="#89b4fa"
        )
        self.hk_help_label.config(
            text="Raccourci assigné ! Cliquez à nouveau pour modifier.",
            fg="#a6e3a1"
        )

    def _reset_default_hotkey(self):
        if self.hotkey_recorder.is_recording:
            self.hotkey_recorder.stop()
        self.current_hotkey = "alt+shift+v"
        self._finish_capture_ui()

    def _on_close(self):
        if self.hotkey_recorder:
            self.hotkey_recorder.stop()
        self.win.destroy()

    def _on_save(self):
        new_config = {}

        # 1. Microphone
        selected_dev_idx = self.mic_combo.current()
        if 0 <= selected_dev_idx < len(self.devices):
            new_config["audio_device"] = self.devices[selected_dev_idx]["index"]

        # 2. Modèle
        sel_model_idx = self.model_combo.current()
        if 0 <= sel_model_idx < len(MODELS):
            new_config["model_size"] = MODELS[sel_model_idx][0]

        # 3. Langue
        sel_lang_idx = self.lang_combo.current()
        if 0 <= sel_lang_idx < len(LANGUAGES):
            new_config["language"] = LANGUAGES[sel_lang_idx][0]

        # 4. Raccourci
        new_config["hotkey"] = self.current_hotkey

        # 5. Mode
        sel_mode_idx = self.mode_combo.current()
        if 0 <= sel_mode_idx < len(MODES):
            new_config["mode"] = MODES[sel_mode_idx][0]

        # 6. Autostart
        new_config["start_with_windows"] = self.autostart_var.get()

        if self.hotkey_recorder:
            self.hotkey_recorder.stop()

        # Appliquer les modifications dans l'application
        self.app.apply_settings(new_config)
        self.win.destroy()
