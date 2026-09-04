import os
import sys
import site
import numpy as np

def init_cuda_dlls():
    """Ajoute dynamiquement tous les répertoires de DLL NVIDIA cuBLAS et cuDNN au chemin de recherche Windows."""
    if sys.platform != "win32":
        return
    try:
        search_bases = []
        try:
            user_site = site.getusersitepackages()
            if user_site and os.path.exists(user_site):
                search_bases.append(user_site)
        except Exception:
            pass
        try:
            for sp in site.getsitepackages():
                if sp and os.path.exists(sp):
                    search_bases.append(sp)
        except Exception:
            pass

        for base in search_bases:
            nvidia_base = os.path.join(base, "nvidia")
            if os.path.isdir(nvidia_base):
                for sub in ["cublas", "cudnn", "cuda_nvrtc", "cuda_runtime"]:
                    bin_dir = os.path.join(nvidia_base, sub, "bin")
                    if os.path.isdir(bin_dir):
                        try:
                            os.add_dll_directory(bin_dir)
                        except Exception:
                            pass
                        if bin_dir not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print(f"[CUDA Init Warning] {e}")

WhisperModel = None

# Liste des hallucinations classiques de Whisper générées sur du silence
SILENCE_HALLUCINATIONS = [
    "sous-titres réalisés par",
    "sous-titrage",
    "amara.org",
    "merci d'avoir regardé",
    "merci d'avoir visionné",
    "merci et à bientôt",
    "à bientôt",
    "transcription :",
]

class Transcriber:
    def __init__(self, model_size="large-v3-turbo", device="cuda", compute_type="float16", language="fr", initial_prompt=None):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.initial_prompt = initial_prompt
        self.model = None
        self._load_model()

    def _load_model(self):
        global WhisperModel
        if WhisperModel is None:
            init_cuda_dlls()
            from faster_whisper import WhisperModel

        print(f"[Whisper] Chargement du modèle '{self.model_size}' sur {self.device} ({self.compute_type})...")
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            # Test de chauffe (warmup) sur un mini tableau pour valider que les DLLs et CUDA répondent réellement
            dummy_audio = np.zeros(1600, dtype=np.float32)
            list(self.model.transcribe(dummy_audio, language="fr")[0])
            print(f"[Whisper] Modèle '{self.model_size}' validé et opérationnel sur {self.device} !")
        except Exception as e:
            print(f"[Whisper Warning] Échec de l'initialisation GPU ({self.device}): {e}")
            if self.device != "cpu":
                print("[Whisper] Bascule automatique de sécurité sur CPU (int8)...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                )
                print(f"[Whisper] Modèle de secours opérationnel sur CPU.")
            else:
                raise e

    def reload_model(self, model_size=None, device=None, compute_type=None, language=None):
        """Recharge dynamiquement un nouveau modèle Whisper."""
        if model_size:
            self.model_size = model_size
        if device:
            self.device = device
        if compute_type:
            self.compute_type = compute_type
        if language is not None:
            self.language = language
        self._load_model()

    def transcribe(self, audio: np.ndarray) -> str:
        if audio is None or len(audio) == 0:
            return ""

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Durée minimale (~0.2s = 3200 échantillons à 16kHz)
        if len(audio) < 3200:
            return ""

        try:
            # Vérifier l'énergie du signal sonore
            max_val = float(np.max(np.abs(audio)))
            if max_val < 0.003:
                # Silence complet ou bruit infime de pièce
                return ""

            # Normalisation audio : amplifier modérément si la voix est basse
            if max_val < 0.25:
                gain = min(0.5 / max_val, 15.0)  # Limiter le gain pour éviter d'exploser le bruit de fond
                audio = audio * gain

            # Définir la langue cible : None active la détection automatique multilingue (français, anglais, etc.)
            target_lang = self.language if (self.language and self.language.lower() != "auto") else None

            segments, info = self.model.transcribe(
                audio,
                language=target_lang,
                beam_size=5,
                vad_filter=False,
                initial_prompt=self.initial_prompt,
            )

            text_parts = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_parts).strip()

            # Filtrage des hallucinations de Whisper sur silence
            if full_text:
                lower_text = full_text.lower()
                if any(h in lower_text for h in SILENCE_HALLUCINATIONS) and max_val < 0.03:
                    return ""

            return full_text
        except Exception as e:
            print(f"[Whisper Error] Erreur de transcription sur {self.device}: {e}")
            # Tentative de secours sur CPU si CUDA rencontre un pépin à l'exécution
            if self.device != "cpu":
                try:
                    print("[Whisper] Bascule immédiate de secours sur CPU...")
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                    target_lang = self.language if (self.language and self.language.lower() != "auto") else None
                    segments, _ = self.model.transcribe(
                        audio,
                        language=target_lang,
                        beam_size=5,
                        vad_filter=False,
                    )
                    text_parts = [segment.text.strip() for segment in segments]
                    return " ".join(text_parts).strip()
                except Exception as fallback_err:
                    print(f"[Whisper Error] Échec du secours CPU: {fallback_err}")
            return ""


