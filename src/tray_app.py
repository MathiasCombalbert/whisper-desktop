import os
import subprocess
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

def create_tray_icon_image(color="#a6e3a1", size=64):
    """Génère une icône circulaire dynamique avec contour."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Cercle principal
    margin = 4
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=color,
        outline="#181825",
        width=3
    )
    # Petit point intérieur façon microphone
    inner_margin = 18
    draw.ellipse(
        (inner_margin, inner_margin, size - inner_margin, size - inner_margin),
        fill="#ffffff"
    )
    return image

class SystemTrayManager:
    def __init__(self, app_controller):
        self.app = app_controller
        self.icon = None
        self.ready_img = create_tray_icon_image("#a6e3a1")       # Vert pastel
        self.recording_img = create_tray_icon_image("#f38ba8")   # Rouge pastel
        self.transcribing_img = create_tray_icon_image("#f9e2af")# Jaune pastel

    def set_state(self, state: str):
        if not self.icon:
            return
        try:
            if state == "recording":
                self.icon.icon = self.recording_img
                self.icon.title = "Speech-to-Text: Enregistrement..."
            elif state == "transcribing":
                self.icon.icon = self.transcribing_img
                self.icon.title = "Speech-to-Text: Transcription Whisper..."
            else:
                self.icon.icon = self.ready_img
                self.icon.title = f"Speech-to-Text: Prêt ({self.app.config.get('hotkey', 'alt+shift+v')})"
        except Exception:
            pass

    def _toggle_mode(self, icon, item_obj):
        current_mode = self.app.config.get("mode", "toggle")
        new_mode = "push_to_talk" if current_mode == "toggle" else "toggle"
        self.app.set_mode(new_mode)

    def _toggle_autostart(self, icon, item_obj):
        current = self.app.is_autostart_active()
        self.app.set_autostart_active(not current)

    def _toggle_bar(self, icon, item_obj):
        self.app.toggle_bar_visibility()

    def _open_config(self, icon, item_obj):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            os.startfile(config_path)
        except Exception as e:
            print(f"[Tray] Erreur ouverture config: {e}")

    def _quit_app(self, icon, item_obj):
        self.app.stop_and_exit()

    def _open_settings(self, icon, item_obj):
        self.app.open_settings()

    def build_menu(self):
        return pystray.Menu(
            item(
                lambda text: f"Raccourci: {self.app.config.get('hotkey', 'alt+shift+v').upper()}",
                lambda icon, item_obj: None,
                enabled=False
            ),
            item(
                lambda text: f"Mode actuel: {self.app.config.get('mode', 'toggle').replace('_', ' ').capitalize()}",
                self._toggle_mode
            ),
            item("Langue de dictée", pystray.Menu(
                item("Français", lambda icon, item_obj: self.app.set_language("fr"), checked=lambda item_obj: self.app.config.get("language") == "fr"),
                item("Anglais", lambda icon, item_obj: self.app.set_language("en"), checked=lambda item_obj: self.app.config.get("language") == "en"),
                item("Automatique (Multilingue)", lambda icon, item_obj: self.app.set_language("auto"), checked=lambda item_obj: self.app.config.get("language") in [None, "auto"]),
            )),
            item("Afficher / Masquer la barre", self._toggle_bar, default=True),
            item("⚙️ Paramètres", self._open_settings),
            pystray.Menu.SEPARATOR,
            item(
                "Lancer au démarrage de Windows",
                self._toggle_autostart,
                checked=lambda item_obj: self.app.is_autostart_active()
            ),
            item("Modifier la configuration (JSON)", self._open_config),
            pystray.Menu.SEPARATOR,
            item("Quitter", self._quit_app)
        )

    def start(self):
        self.icon = pystray.Icon(
            "speech_to_text_whisper",
            self.ready_img,
            f"Speech-to-Text: Prêt ({self.app.config.get('hotkey', 'alt+shift+v')})",
            menu=self.build_menu()
        )
        self.icon.run_detached()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
