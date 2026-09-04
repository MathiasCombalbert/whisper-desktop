import threading
import numpy as np
import sounddevice as sd
import queue

def clean_device_name(raw_name: str) -> str:
    """Nettoie le nom Windows d'un périphérique audio pour un affichage compact et clair."""
    name = raw_name.strip()
    if name.startswith("Microphone (") and name.endswith(")"):
        name = name[12:-1].strip()
    elif name.startswith("Micro (") and name.endswith(")"):
        name = name[7:-1].strip()

    low = name.lower()
    if "voicemeeter" in low:
        if "aux" in low:
            return "VoiceMeeter Aux"
        if "vaio3" in low:
            return "VoiceMeeter VAIO3"
        return "VoiceMeeter"
    if "cable output" in low:
        return "VB-Audio Cable"
    return name

class AudioRecorder:
    def __init__(self, target_sample_rate=16000, device=None):
        self.target_sample_rate = target_sample_rate
        self.preferred_device = device
        self.recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self._lock = threading.Lock()
        self.current_volume = 0.0

        # Résolution du périphérique UNE SEULE FOIS au démarrage pour être instantané
        self.active_device_index = self._find_best_input_device()
        self.native_sample_rate = 48000
        self.device_name = "Microphone"
        self._init_device_info()

    def _init_device_info(self):
        try:
            dev_info = sd.query_devices(self.active_device_index)
            self.native_sample_rate = int(dev_info.get('default_samplerate', 48000))
            raw_name = dev_info.get("name", "Microphone")
            self.device_name = clean_device_name(raw_name)
            print(f"[Audio] Périphérique sélectionné: [{self.active_device_index}] {self.device_name} ({raw_name}) @ {self.native_sample_rate}Hz")
        except Exception as e:
            print(f"[Audio Warning] Info périphérique: {e}")

    def get_active_device_name(self) -> str:
        return self.device_name

    def switch_device(self, device_index: int):
        """Bascule immédiatement vers un autre périphérique d'entrée."""
        with self._lock:
            was_recording = self.recording
            if was_recording and self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            self.active_device_index = device_index
            self.preferred_device = device_index
            self._init_device_info()

            if was_recording:
                try:
                    self.stream = sd.InputStream(
                        device=self.active_device_index,
                        samplerate=self.native_sample_rate,
                        channels=1,
                        dtype="float32",
                        callback=self._callback,
                    )
                    self.stream.start()
                except Exception as e:
                    self.recording = False
                    print(f"[Audio Error] Redémarrage micro [{self.active_device_index}]: {e}")

    @staticmethod
    def get_available_devices():
        """Retourne la liste des périphériques audio d'entrée valides (WASAPI en priorité)."""
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        wasapi_devices = []
        other_devices = []

        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                api_name = hostapis[d['hostapi']]['name'].lower()
                if "wdm-ks" in api_name or "wdm" in api_name:
                    continue

                cname = clean_device_name(d['name'])
                entry = {
                    "index": i,
                    "name": cname,
                    "raw_name": d['name'],
                    "api": hostapis[d['hostapi']]['name'],
                    "samplerate": int(d.get('default_samplerate', 48000))
                }
                if "wasapi" in api_name:
                    wasapi_devices.append(entry)
                else:
                    other_devices.append(entry)

        result = []
        seen_names = set()
        for entry in wasapi_devices:
            if entry["name"] not in seen_names:
                seen_names.add(entry["name"])
                result.append(entry)

        for entry in other_devices:
            if entry["name"] not in seen_names and not any(v in entry["name"].lower() for v in ["mappeur", "capture audio principal"]):
                seen_names.add(entry["name"])
                result.append(entry)

        return result

    def _find_best_input_device(self):
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        # 1. Si un périphérique spécifique est demandé
        if self.preferred_device is not None:
            if isinstance(self.preferred_device, int) and 0 <= self.preferred_device < len(devices):
                return self.preferred_device
            if isinstance(self.preferred_device, str):
                search_term = self.preferred_device.lower()
                for i, d in enumerate(devices):
                    if d['max_input_channels'] > 0 and search_term in d['name'].lower():
                        return i

        # 2. Prioriser WASAPI. EXCLURE formellement WDM-KS.
        candidates = []
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                api_name = hostapis[d['hostapi']]['name'].lower()
                name = d['name'].lower()

                # Ignorer impérativement WDM-KS
                if "wdm-ks" in api_name or "wdm" in api_name:
                    continue

                is_virtual = any(v in name for v in ["cable", "voicemeeter", "mixage", "stereo mix"])
                score = 0
                if "wasapi" in api_name:
                    score += 60
                elif "directsound" in api_name:
                    score += 20
                if any(k in name for k in ["micro", "mic", "input", "headset", "casque"]):
                    score += 35
                if is_virtual:
                    score -= 50
                candidates.append((score, i, d))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return sd.default.device[0]

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            try:
                # Éviter tout NaN
                data_clean = np.nan_to_num(indata, nan=0.0)
                peak = float(np.max(np.abs(data_clean)))
                self.current_volume = peak
            except Exception:
                self.current_volume = 0.0
            self.audio_queue.put(indata.copy())

    def start(self):
        with self._lock:
            if self.recording:
                return

            self.recording = True
            # Vider la file d'attente
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            try:
                extra = None
                try:
                    hostapis = sd.query_hostapis()
                    dev_info = sd.query_devices(self.active_device_index)
                    if "wasapi" in hostapis[dev_info['hostapi']]['name'].lower():
                        extra = sd.WasapiSettings(exclusive=False)
                except Exception:
                    pass

                self.stream = sd.InputStream(
                    device=self.active_device_index,
                    samplerate=self.native_sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                    extra_settings=extra,
                )
                self.stream.start()
            except Exception as e:
                try:
                    self.stream = sd.InputStream(
                        device=self.active_device_index,
                        samplerate=self.native_sample_rate,
                        channels=1,
                        dtype="float32",
                        callback=self._callback,
                    )
                    self.stream.start()
                except Exception as e2:
                    self.recording = False
                    raise RuntimeError(f"Démarrage micro [{self.active_device_index}]: {e2}")

    def stop(self) -> np.ndarray:
        with self._lock:
            if not self.recording:
                return np.array([], dtype=np.float32)
            self.recording = False
            self.current_volume = 0.0
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

        chunks = []
        while not self.audio_queue.empty():
            try:
                chunks.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not chunks:
            return np.array([], dtype=np.float32)

        raw_audio = np.concatenate(chunks, axis=0).flatten()
        raw_audio = np.nan_to_num(raw_audio, nan=0.0)

        # Rééchantillonner à 16000 Hz si nécessaire
        if self.native_sample_rate != self.target_sample_rate and len(raw_audio) > 0:
            target_length = int(len(raw_audio) * self.target_sample_rate / self.native_sample_rate)
            indices = np.linspace(0, len(raw_audio) - 1, target_length)
            audio_16k = np.interp(indices, np.arange(len(raw_audio)), raw_audio).astype(np.float32)
            return audio_16k

        return raw_audio
