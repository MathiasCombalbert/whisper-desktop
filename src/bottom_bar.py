import tkinter as tk
import sys
import time
import math
import pyperclip

if sys.platform == "win32":
    import ctypes
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST = 0x00000008

class BottomBarHUD:
    """
    Barre d'état moderne, discrète et flottante en bas de l'écran.
    Grâce à WS_EX_NOACTIVATE et takefocus=0, cliquer dessus NE VOLE JAMAIS LE FOCUS d'Antigravity.
    Se cache en arrière-plan et consomme 0.0% de CPU au repos.
    """
    def __init__(self, app_controller):
        self.app = app_controller
        self.root = None
        self.bar_hwnd = None
        self.status_dot = None
        self.status_label = None
        self.mic_label = None
        self.vu_canvas = None
        self.action_btn = None
        self.preview_label = None
        self.hotkey_badge = None

        self.is_visible = False
        self._start_time = None
        self._timer_job = None
        self._vu_job = None
        self._auto_hide_job = None
        self._blink_state = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._last_raw_text = ""

    def create_window(self):
        self.root = tk.Tk()
        self.root.title("SpeechToText Bar")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg="#11111b", takefocus=0)

        # Dimensions & positionnement en bas au centre
        width, height = 650, 56
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - width) // 2
        y = sh - 115
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.root.update_idletasks()

        # EMPÊCHER STRICTEMENT LE VOL DE FOCUS AU CLIC (WS_EX_NOACTIVATE sur Windows)
        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if not hwnd:
                    hwnd = self.root.winfo_id()
                self.bar_hwnd = hwnd
                ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
            except Exception as e:
                print(f"[HUD Warning] Style NoActivate: {e}")

        # Conteneur principal (takefocus=0)
        self.container = tk.Frame(self.root, bg="#181825", highlightbackground="#313244", highlightthickness=1, takefocus=0)
        self.container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Glisser-déposer pour repositionner librement la barre
        self.container.bind("<ButtonPress-1>", self._start_drag)
        self.container.bind("<B1-Motion>", self._on_drag)

        # 1. Section GAUCHE : Indicateur et Statut
        left_frame = tk.Frame(self.container, bg="#181825", takefocus=0)
        left_frame.pack(side=tk.LEFT, padx=(12, 8), pady=4)
        left_frame.bind("<ButtonPress-1>", self._start_drag)
        left_frame.bind("<B1-Motion>", self._on_drag)

        self.dot_canvas = tk.Canvas(left_frame, width=14, height=14, bg="#181825", highlightthickness=0, takefocus=0)
        self.dot_canvas.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_id = self.dot_canvas.create_oval(3, 3, 11, 11, fill="#a6e3a1", outline="")

        self.status_label = tk.Label(
            left_frame,
            text="Prêt",
            font=("Segoe UI", 9, "bold"),
            fg="#a6e3a1",
            bg="#181825",
            width=8,
            anchor="w",
            takefocus=0
        )
        self.status_label.pack(side=tk.LEFT)

        # Séparateur vertical
        sep1 = tk.Frame(self.container, bg="#313244", width=1, height=34, takefocus=0)
        sep1.pack(side=tk.LEFT, padx=6)

        # 2. Section CENTRALE : Micro & VU-Mètre / Dernier texte
        center_frame = tk.Frame(self.container, bg="#181825", takefocus=0)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        center_frame.bind("<ButtonPress-1>", self._start_drag)
        center_frame.bind("<B1-Motion>", self._on_drag)

        top_center = tk.Frame(center_frame, bg="#181825", takefocus=0)
        top_center.pack(fill=tk.X)
        top_center.bind("<ButtonPress-1>", self._start_drag)
        top_center.bind("<B1-Motion>", self._on_drag)

        # Micro & sélecteur déroulant
        mic_box = tk.Frame(top_center, bg="#181825", cursor="hand2", takefocus=0)
        mic_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.mic_label = tk.Label(
            mic_box,
            text="🎙️ Détection micro...",
            font=("Segoe UI", 8, "bold"),
            fg="#cdd6f4",
            bg="#181825",
            anchor="w",
            cursor="hand2",
            takefocus=0
        )
        self.mic_label.pack(side=tk.LEFT)

        self.mic_arrow = tk.Label(
            mic_box,
            text=" ▾",
            font=("Segoe UI", 8, "bold"),
            fg="#89b4fa",
            bg="#181825",
            cursor="hand2",
            takefocus=0
        )
        self.mic_arrow.pack(side=tk.LEFT)

        # Hover interactif sur le sélecteur micro
        def _mic_enter(e):
            self.mic_label.config(fg="#89b4fa")
            self.mic_arrow.config(fg="#b4befe")
        def _mic_leave(e):
            self.mic_label.config(fg="#cdd6f4")
            self.mic_arrow.config(fg="#89b4fa")

        for w in [mic_box, self.mic_label, self.mic_arrow]:
            w.bind("<Button-1>", self._on_mic_clicked)
            w.bind("<Enter>", _mic_enter)
            w.bind("<Leave>", _mic_leave)

        # Mini VU-mètre audio
        self.vu_canvas = tk.Canvas(top_center, width=80, height=8, bg="#26273a", highlightthickness=0, takefocus=0)
        self.vu_canvas.pack(side=tk.RIGHT, padx=(4, 0))
        self.vu_bar = self.vu_canvas.create_rectangle(0, 0, 0, 8, fill="#a6e3a1", outline="")

        # Ligne d'aperçu du texte dicté (cliquable pour copier manuellement)
        self.preview_label = tk.Label(
            center_frame,
            text="Appuyez sur votre raccourci ou Parler pour dicter...",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#181825",
            anchor="w",
            cursor="hand2",
            takefocus=0
        )
        self.preview_label.pack(fill=tk.X, pady=(2, 0))
        self.preview_label.bind("<Button-1>", self._on_preview_clicked)

        # Séparateur vertical
        sep2 = tk.Frame(self.container, bg="#313244", width=1, height=34, takefocus=0)
        sep2.pack(side=tk.LEFT, padx=6)

        # 3. Section DROITE : Bouton d'action, Molette Paramètres et Fermer
        right_frame = tk.Frame(self.container, bg="#181825", takefocus=0)
        right_frame.pack(side=tk.RIGHT, padx=(6, 10), pady=4)

        # Bouton Principal (Parler / Coller) - Design moderne et épuré
        self.action_btn = tk.Button(
            right_frame,
            text="🎙️ Parler",
            font=("Segoe UI", 9, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            activeforeground="#11111b",
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=3,
            cursor="hand2",
            takefocus=0,
            command=self._on_action_clicked
        )
        self.action_btn.pack(side=tk.LEFT, padx=(0, 6))

        def _action_enter(e):
            if self.app.is_recording:
                self.action_btn.config(bg="#eba0ac")
            elif not self.app.is_transcribing:
                self.action_btn.config(bg="#b4befe")

        def _action_leave(e):
            if self.app.is_recording:
                self.action_btn.config(bg="#f38ba8")
            elif not self.app.is_transcribing:
                self.action_btn.config(bg="#89b4fa")

        self.action_btn.bind("<Enter>", _action_enter)
        self.action_btn.bind("<Leave>", _action_leave)

        # Molette Paramètres ⚙️
        settings_btn = tk.Button(
            right_frame,
            text="⚙️",
            font=("Segoe UI", 10),
            bg="#181825",
            fg="#a6adc8",
            activebackground="#313244",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
            takefocus=0,
            command=self._on_settings_clicked
        )
        settings_btn.pack(side=tk.LEFT, padx=(0, 4))
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(bg="#313244", fg="#cdd6f4"))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(bg="#181825", fg="#a6adc8"))

        # Bouton Fermer vers le Tray (seul bouton de fermeture conservé)
        close_btn = tk.Button(
            right_frame,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg="#181825",
            fg="#7f849c",
            activebackground="#e78284",
            activeforeground="#11111b",
            relief=tk.FLAT,
            bd=0,
            padx=7,
            pady=2,
            cursor="hand2",
            takefocus=0,
            command=self.hide_to_tray
        )
        close_btn.pack(side=tk.LEFT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#e78284", fg="#11111b"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#181825", fg="#7f849c"))

        # Afficher la barre au lancement pour confirmer le démarrage à l'écran
        self.restore_from_tray()
        self._schedule_auto_hide(seconds=15)

    def _on_preview_clicked(self, event):
        """Permet de copier manuellement le texte transcrit en cliquant dessus."""
        if self._last_raw_text:
            try:
                pyperclip.copy(self._last_raw_text)
                old_text = self.preview_label.cget("text")
                self.preview_label.config(text="📋 Copié dans le presse-papier !", fg="#a6e3a1")
                self.root.after(1500, lambda: self.preview_label.config(text=old_text, fg="#a6e3a1"))
            except Exception:
                pass

    def _on_mic_clicked(self, event=None):
        """Ouvre un menu contextuel affichant les microphones disponibles pour changer en 1 clic."""
        self._cancel_auto_hide()
        try:
            menu = tk.Menu(
                self.root,
                tearoff=0,
                bg="#181825",
                fg="#cdd6f4",
                activebackground="#313244",
                activeforeground="#89b4fa",
                bd=1,
                relief=tk.FLAT,
                font=("Segoe UI", 9)
            )
            devices = self.app.recorder.get_available_devices()
            cur_idx = self.app.recorder.active_device_index

            for dev in devices:
                dev_idx = dev["index"]
                check = "✓ " if dev_idx == cur_idx else "    "
                label_text = f"{check}{dev['name']}"
                menu.add_command(
                    label=label_text,
                    command=lambda i=dev_idx: self.app.switch_microphone(i)
                )

            x = self.mic_label.winfo_rootx()
            y = self.mic_label.winfo_rooty() + self.mic_label.winfo_height() + 2
            menu.post(x, y)
        except Exception as e:
            print(f"[HUD Warning] Erreur menu micro: {e}")

    def _on_settings_clicked(self):
        self._cancel_auto_hide()
        self.app.open_settings()

    def set_mic_name(self, name: str):
        if self.mic_label and self.root:
            clean = name.strip()
            max_len = 22
            display_name = clean if len(clean) <= max_len else clean[:max_len - 3] + "..."
            try:
                self.root.after(0, lambda: self.mic_label.config(text=f"🎙️ {display_name}"))
            except Exception:
                pass

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        try:
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_action_clicked(self):
        self._cancel_auto_hide()
        self.app.on_manual_action()

    def show_recording(self):
        if not self.root:
            return
        self._cancel_auto_hide()
        if not self.is_visible:
            self.restore_from_tray()

        try:
            self._start_time = time.time()
            self.status_label.config(text="00:00", fg="#f38ba8")
            self.dot_canvas.itemconfig(self.dot_id, fill="#f38ba8")
            self.action_btn.config(text="✓ Coller", bg="#f38ba8", activebackground="#eba0ac")
            self.preview_label.config(text="Parlez maintenant, dictée en cours...", fg="#f9e2af", font=("Segoe UI", 8, "normal"))
            self._update_recording_timer()
            self._ensure_vu_loop()
        except Exception:
            pass

    def _update_recording_timer(self):
        if not self.app.is_recording or not self._start_time or not self.root:
            return
        try:
            elapsed = int(time.time() - self._start_time)
            m, s = divmod(elapsed, 60)
            time_str = f"{m:02d}:{s:02d}"

            self._blink_state = not self._blink_state
            dot_color = "#f38ba8" if self._blink_state else "#181825"
            self.dot_canvas.itemconfig(self.dot_id, fill=dot_color)
            self.status_label.config(text=time_str)

            self._timer_job = self.root.after(500, self._update_recording_timer)
        except Exception:
            pass

    def show_transcribing(self):
        if not self.root:
            return
        try:
            if self._timer_job:
                try:
                    self.root.after_cancel(self._timer_job)
                except Exception:
                    pass
                self._timer_job = None

            self.status_label.config(text="Calcul...", fg="#f9e2af")
            self.dot_canvas.itemconfig(self.dot_id, fill="#f9e2af")
            self.action_btn.config(text="⏳ Calcul...", bg="#45475a")
            self.preview_label.config(text="Transcription GPU en cours...", fg="#f9e2af")
        except Exception:
            pass

    def show_ready(self, last_text=None, status_msg="Prêt"):
        if not self.root:
            return
        try:
            if self._timer_job:
                try:
                    self.root.after_cancel(self._timer_job)
                except Exception:
                    pass
                self._timer_job = None

            self.status_label.config(text=status_msg, fg="#a6e3a1")
            self.dot_canvas.itemconfig(self.dot_id, fill="#a6e3a1")
            self.action_btn.config(text="🎙️ Parler", bg="#89b4fa", activebackground="#b4befe")

            self.vu_canvas.coords(self.vu_bar, 0, 0, 0, 8)

            if last_text:
                self._last_raw_text = last_text
                display_text = f"💬 \"{last_text}\""
                if len(display_text) > 55:
                    display_text = display_text[:52] + "...\""
                self.preview_label.config(text=display_text, fg="#a6e3a1", font=("Segoe UI", 8, "normal"))
            elif last_text == "":
                self.preview_label.config(text="Aucune voix détectée. Réessayez.", fg="#fab387", font=("Segoe UI", 8, "italic"))

            # Programmer le repli automatique en arrière-plan après 15 secondes d'inactivité
            self._schedule_auto_hide(seconds=15)
        except Exception:
            pass

    def _schedule_auto_hide(self, seconds=15):
        self._cancel_auto_hide()
        if self.root:
            self._auto_hide_job = self.root.after(int(seconds * 1000), self.hide_to_tray)

    def _cancel_auto_hide(self):
        if self._auto_hide_job and self.root:
            try:
                self.root.after_cancel(self._auto_hide_job)
            except Exception:
                pass
            self._auto_hide_job = None

    def _ensure_vu_loop(self):
        if self._vu_job is None:
            self._start_vu_loop()

    def _start_vu_loop(self):
        """Met à jour le niveau de volume uniquement pendant l'enregistrement (0% CPU au repos)."""
        if not self.root or not self.is_visible:
            self._vu_job = None
            return

        if self.app.is_recording and hasattr(self.app.recorder, "current_volume"):
            try:
                vol = self.app.recorder.current_volume
                if math.isnan(vol) or math.isinf(vol):
                    vol = 0.0
                level = min(1.0, vol * 6.0)
                bar_w = int(level * 80)
                fill_col = "#a6e3a1" if level < 0.7 else ("#f9e2af" if level < 0.9 else "#f38ba8")
                self.vu_canvas.coords(self.vu_bar, 0, 0, bar_w, 8)
                self.vu_canvas.itemconfig(self.vu_bar, fill=fill_col)
            except Exception:
                pass
            self._vu_job = self.root.after(60, self._start_vu_loop)
        else:
            self.vu_canvas.coords(self.vu_bar, 0, 0, 0, 8)
            self._vu_job = None

    def hide_to_tray(self):
        """Passe l'application en arrière-plan complet (0% CPU)."""
        self.is_visible = False
        self._cancel_auto_hide()
        if self._vu_job and self.root:
            try:
                self.root.after_cancel(self._vu_job)
            except Exception:
                pass
            self._vu_job = None

        if self.root:
            try:
                self.root.withdraw()
            except Exception:
                pass

        # Libérer immédiatement la mémoire quand on remet en arrière-plan
        if hasattr(self, "app") and self.app:
            try:
                self.app.unload_transcriber()
            except Exception:
                pass

    def restore_from_tray(self):
        """Fait réapparaître la barre instantanément au premier plan."""
        self.is_visible = True
        self._cancel_auto_hide()
        if self.root:
            try:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
                self.root.lift()
                if sys.platform == "win32" and self.bar_hwnd:
                    HWND_TOPMOST = -1
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    SWP_NOACTIVATE = 0x0010
                    ctypes.windll.user32.SetWindowPos(
                        self.bar_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
                    )
            except Exception:
                pass


    def show_loading(self, message="Chargement du modèle Whisper..."):
        if not self.root:
            return
        try:
            self.status_label.config(text="Init...", fg="#f9e2af")
            self.dot_canvas.itemconfig(self.dot_id, fill="#f9e2af")
            self.action_btn.config(text="⏳ Chargement", bg="#45475a", activebackground="#45475a")
            self.preview_label.config(text=message, fg="#f9e2af", font=("Segoe UI", 8, "italic"))
        except Exception:
            pass

    def show_loading_safe(self, message="Chargement du modèle Whisper..."):
        if self.root:
            self.root.after(0, lambda: self.show_loading(message))

    def show_recording_safe(self):
        if self.root:
            self.root.after(0, self.show_recording)

    def show_transcribing_safe(self):
        if self.root:
            self.root.after(0, self.show_transcribing)

    def show_ready_safe(self, last_text=None, status_msg="Prêt"):
        if self.root:
            self.root.after(0, lambda: self.show_ready(last_text, status_msg))
