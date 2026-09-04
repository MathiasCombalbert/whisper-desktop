# 🎙️ Whisper Desktop

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://www.microsoft.com/windows)
[![Engine](https://img.shields.io/badge/Engine-faster--whisper%20(CTranslate2)-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![CUDA](https://img.shields.io/badge/Hardware-NVIDIA%20CUDA%20%2F%20CPU%20Fallback-76B900.svg)](https://developer.nvidia.com/cuda-zone)

**A minimalist, high-performance Windows speech-to-text desktop assistant powered by local OpenAI Whisper.**  
*Dictate anywhere with a global hotkey, auto-paste directly into your active app without losing focus, and enjoy 0.0% CPU usage when idle.*

[Key Features](#-key-features) • [Installation](#-installation) • [How to Use](#-how-to-use) • [Configuration](#-configuration) • [Architecture](#-architecture) • [License](#-license)

</div>

---

## ✨ Overview

**Whisper Desktop** is designed for developers, writers, and power users who want seamless, instant voice dictation directly into their tools (VS Code, Antigravity, Discord, browsers, terminals) with **zero latency**, **zero telemetry**, and **zero cloud dependency**.

Unlike heavy voice assistants that stay in the foreground or consume significant resources in the background, Whisper Desktop runs as an ultra-light tray application:
- Press your global shortcut (**`Alt + Shift + V`**) anywhere.
- Speak naturally.
- The transcribed text is automatically pasted at your cursor position via Win32 API injection, **preserving the exact focus of your active application**.
- The floating HUD disappears back into the system tray after dictation, consuming **0.0% CPU**.

---

## 🚀 Key Features

- **⚡ Local GPU Acceleration (`faster-whisper` on CUDA)**  
  Blazing-fast transcription (~0.5s for typical sentences) utilizing NVIDIA Tensor Cores (`float16`). Automated fail-safe fallback to CPU (`int8`) on non-NVIDIA machines.

- **🎯 Focus-Preserving Direct Injection**  
  Uses native Win32 `AttachThreadInput` and `SetForegroundWindow` hooks to paste text (`Ctrl + V`) directly into Electron apps, code editors, and input fields without ever blurring or stealing window focus.

- **🔋 Zero Idle Resource Usage (0.0% CPU)**  
  When resting in the Windows System Tray, all polling and VU-meter rendering loops are completely suspended.

- **🎛️ Minimalist Passive HUD & Audio VU-Meter**  
  A non-intrusive floating bar (`WS_EX_NOACTIVATE`) displays real-time recording duration, live microphone input level (VU meter), and recent transcription preview.

- **🎙️ 1-Click Dynamic Microphone Switcher**  
  Switch instantly between your studio mic and webcam headset with a clean dropdown menu without restarting the app.

- **⚙️ Built-in Graphical Settings**  
  Adjust Whisper model size (`large-v3-turbo`, `medium`, `small`, `base`, `tiny`), transcription language, global hotkey, trigger mode (*Toggle* vs *Push-to-Talk*), and Windows startup with a single click.

- **🛡️ 100% Private & Offline**  
  Audio is processed entirely locally on your machine. No voice recordings or text ever leave your computer.

---

## 📦 Installation

### Option 1: Quick Install (Recommended)

1. Clone or download this repository:
   ```bash
   git clone https://github.com/MathiasCombalbert/whisper-desktop.git
   cd whisper-desktop
   ```

2. Run the one-click Windows installer:
   ```cmd
   install.bat
   ```
   *This automatically sets up the required Python packages and CUDA bindings.*

### Option 2: Manual Setup

Ensure you have **Python 3.10+** (64-bit) installed, then run:

```bash
pip install -r requirements.txt
```

---

## 🎮 How to Use

1. **Launch the Application**:
   - Double-click **`run_silent.vbs`** to start silently in the Windows System Tray (recommended).
   - Or double-click **`run_debug.bat`** to run with a live console log.

2. **Dictate Anywhere**:
   - Place your cursor in any application (editor, browser, chat).
   - Press **`Alt + Shift + V`** (or click `🎙️ Parler`).
   - Speak your thoughts.
   - Press **`Alt + Shift + V`** again (or click `✓ Coller`).
   - The transcribed text is instantly pasted right at your cursor!

3. **Customize & Minimize**:
   - Click **`—`** (minimize) to hide the floating HUD back to the tray.
   - Click **`⚙️`** to configure hotkeys, Whisper models, or input devices.
   - Double-click the tray icon to toggle the HUD.

---

## ⚙️ Configuration

Settings can be modified directly via the in-app **`⚙️` Settings** window, or by editing `config.json`:

```json
{
  "hotkey": "alt+shift+v",
  "mode": "toggle",
  "model_size": "large-v3-turbo",
  "device": "cuda",
  "compute_type": "float16",
  "language": null,
  "preserve_clipboard": false,
  "sound_feedback": false,
  "show_overlay": true,
  "auto_hide_seconds": 15,
  "audio_device": null,
  "start_with_windows": false,
  "initial_prompt": "Transcription en français pour le code, programmation, prompts, coller, copier, IA."
}
```

| Setting | Type | Description |
| :--- | :--- | :--- |
| `hotkey` | string | Global Windows key combination (e.g. `alt+shift+v`, `ctrl+shift+space`) |
| `mode` | string | Trigger mode: `"toggle"` (press once to start, again to paste) or `"push_to_talk"` |
| `model_size` | string | Whisper model: `"large-v3-turbo"`, `"medium"`, `"small"`, `"base"`, `"tiny"` |
| `device` | string | Inference backend: `"cuda"` (NVIDIA GPU) or `"cpu"` |
| `language` | string/null | Target language code (`"fr"`, `"en"`, etc.) or `null` for automatic multilingual detection |
| `auto_hide_seconds` | int | Inactivity delay in seconds before the HUD automatically hides to tray |

---

## 🏗️ Architecture

```
whisper-desktop/
├── app.py                # Main application orchestrator & background thread manager
├── audio_recorder.py     # Resilient WASAPI audio capture & dynamic device switcher
├── transcriber.py        # faster-whisper CTranslate2 engine with dynamic CUDA DLL loader
├── bottom_bar.py         # Non-activating floating HUD bar (WS_EX_NOACTIVATE) & VU meter
├── settings_dialog.py    # Native dark-themed configuration dialog
├── paster.py             # Win32 AttachThreadInput focus-preserving keyboard injector
├── tray_app.py           # Windows System Tray integration (pystray)
├── autostart.py          # Windows Startup registry / shortcut manager
├── config.json           # Application preferences
├── requirements.txt      # Python dependencies
├── install.bat           # 1-click Windows setup script
├── run_silent.vbs        # Background launch script (zero console window)
└── run_debug.bat         # Diagnostic launcher with stdout logging
```

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

Copyright (c) 2026 **Mathias Combalbert**
