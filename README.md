# Whisper Desktop

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-0078D6.svg)](https://github.com/MathiasCombalbert/whisper-desktop)
[![Engine](https://img.shields.io/badge/Engine-faster--whisper%20(CTranslate2)-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Hardware](https://img.shields.io/badge/Hardware-NVIDIA%20CUDA%20%2F%20CPU%20Fallback-76B900.svg)](https://developer.nvidia.com/cuda-zone)

**A minimalist, high-performance speech-to-text desktop assistant powered by local OpenAI Whisper for Windows and Linux.**  
*Dictate anywhere with a global shortcut, auto-paste directly into your active window without losing focus, and maintain 0.0% CPU usage when idle.*

[Overview](#overview) • [Key Features](#key-features) • [Installation](#installation) • [Compilation](#compilation) • [How to Use](#how-to-use) • [Configuration](#configuration) • [Architecture](#architecture) • [License](#license)

</div>

---

## Overview

Whisper Desktop is a local dictation utility for Windows designed for developers, writers, and power users who require fast, offline speech-to-text directly into any text field (code editors, browsers, terminals, chat clients).

Key design principles:
- **Instant access**: Press a configurable global shortcut (`Alt + Shift + V` by default) to start recording.
- **Focus preservation**: Transcribed text is pasted into the active application via Win32 API injection without blurring or shifting window focus.
- **Zero idle impact**: The floating HUD and background processes consume 0.0% CPU cycles while waiting in the system tray.
- **Complete privacy**: All processing occurs locally on your machine via CTranslate2. No audio or text data is transmitted over the network.

---

## Key Features

- **Hardware Acceleration with Fail-Safe Fallback**  
  Utilizes `faster-whisper` and NVIDIA CUDA Tensor Cores (`float16`) for sub-second transcription. Automatically switches to CPU (`int8`) execution if CUDA is unavailable.

- **Focus-Preserving Direct Injection**  
  Employs Win32 `AttachThreadInput` and synthetic input events to paste text into target windows seamlessly, preventing focus loss in Electron applications, IDEs, and browser forms.

- **Passive Floating HUD**  
  Built with native Windows non-activating flags (`WS_EX_NOACTIVATE`) so clicking interface controls does not steal window focus. Features an animated audio VU meter, status indicator, and preview label.

- **Interactive Keybind Configuration**  
  Assign shortcuts directly in the settings interface by pressing your desired key combination (similar to game controls), without needing to type key names manually.

- **Dynamic Audio Device Selection**  
  Switch between connected microphones on the fly via a dropdown menu on the HUD bar. Employs shared WASAPI mode to prevent audio device lockups.

- **Zero Idle Resource Consumption**  
  Background polling loops and audio capture threads are suspended when the application is idle in the system tray.

---

## Installation

### Method 1: Automatic Setup (Recommended)

1. Clone or download this repository:
   ```cmd
   git clone https://github.com/MathiasCombalbert/whisper-desktop.git
   cd whisper-desktop
   ```

2. Run the one-click installer:
   ```cmd
   install.bat
   ```
   *This validates your Python environment and installs all dependencies with CUDA support.*

### Method 2: Manual Setup

Ensure Python 3.10 or higher (64-bit) is installed, then run:

```bash
pip install -r requirements.txt
```

---

## Compilation

Whisper Desktop can be packaged into standalone native binaries for Windows and Linux without requiring a pre-installed Python interpreter on the target system.

### Compiling on Windows

- **Via Interactive Manager**: Run `install.bat` and select `[2] Compiler l'executable Windows`.
- **Direct Build Script**:
  ```cmd
  build_windows.bat
  ```
  The standalone bundle will be generated in `dist/WhisperDesktop/WhisperDesktop.exe`.

### Compiling for Linux

#### Option A: Cross-Compiling via Docker (Recommended from Windows)
Requires Docker Desktop installed and running:
- Run `install.bat` and select `[3] Compiler pour Linux via Docker`, or run:
  ```cmd
  build_linux.bat
  ```
  The compiled archive `WhisperDesktop-Linux-x64.tar.gz` will be placed in `dist/linux/`.

#### Option B: Native Linux Compilation
On an Ubuntu / Debian system:
```bash
sudo apt-get install -y portaudio19-dev libasound2-dev libx11-dev xdotool python3-tk patchelf
chmod +x build_linux.sh
./build_linux.sh
```

---

## How to Use

1. **Start the Application**:
   - Double-click `run.bat` to launch the application silently into the system tray.
   - Alternatively, run `run_debug.bat` to inspect live console logs and transcription metrics.

2. **Dictate**:
   - Focus your cursor in any editor or input area.
   - Press `Alt + Shift + V` (or click the dictation button on the HUD).
   - Speak your text.
   - Press `Alt + Shift + V` again to finalize.
   - The transcribed text is pasted immediately at your cursor position.

3. **Manage & Customize**:
   - Click `-` to minimize the HUD back to the system tray.
   - Click the gear icon to open the configuration dialog and change the shortcut, Whisper model, language, or audio device.
   - Double-click the system tray icon to toggle HUD visibility.

---

## Configuration

Settings can be managed through the built-in graphical dialog or edited in `config.json`:

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

### Parameter Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `hotkey` | string | `"alt+shift+v"` | Global keyboard combination |
| `mode` | string | `"toggle"` | Trigger mode: `"toggle"` or `"push_to_talk"` |
| `model_size` | string | `"large-v3-turbo"` | Whisper model size (`large-v3-turbo`, `medium`, `small`, `base`, `tiny`) |
| `device` | string | `"cuda"` | Execution device (`"cuda"` or `"cpu"`) |
| `compute_type` | string | `"float16"` | Precision type (`"float16"` for GPU, `"int8"` for CPU) |
| `language` | string/null | `null` | Language code (e.g. `"fr"`, `"en"`) or `null` for automatic detection |
| `auto_hide_seconds` | integer | `15` | Seconds of inactivity before the HUD minimizes to tray |
| `audio_device` | integer/null | `null` | Selected input device index or `null` for system default |
| `start_with_windows` | boolean | `false` | Launch automatically upon Windows user logon |

---

## Architecture

```
whisper-desktop/
├── src/                          # Application source code
│   ├── app.py                    # Application controller and background event loop
│   ├── audio_recorder.py         # Audio streaming and dynamic input selection
│   ├── transcriber.py            # faster-whisper CTranslate2 inference engine
│   ├── bottom_bar.py             # Passive floating HUD (WS_EX_NOACTIVATE)
│   ├── settings_dialog.py        # Configuration dialog with interactive keybind recorder
│   ├── paster.py                 # Focus-preserving keyboard injector (Windows & Linux)
│   ├── tray_app.py               # System tray integration
│   └── autostart.py              # OS startup registration manager
├── .github/                      # CI/CD pipelines
│   └── workflows/
│       └── release.yml           # Automated Windows & Linux binary releases
├── Dockerfile.linux              # Containerized Linux build specification
├── build_linux.sh                # Native Linux build script
├── build_linux.bat               # Windows wrapper for Docker Linux compilation
├── build_windows.bat             # Standalone Windows PyInstaller build script
├── config.json                   # Application configuration file
├── requirements.txt              # Python package dependencies
├── install.bat                   # Interactive setup and build manager
├── run.bat                       # Primary one-click launcher
├── run_debug.bat                 # Diagnostic console launcher
├── run_silent.vbs                # Background startup script
├── .gitignore                    # Version control ignore definitions
├── LICENSE                       # MIT License
└── README.md                     # Project documentation
```

---

## License

This project is licensed under the **MIT License**. See the [`LICENSE`](LICENSE) file for details.

Copyright (c) 2026 **Mathias Combalbert**
