# LocalTTS v3.1

> High-quality offline text-to-speech powered by the **Kokoro-82M** neural engine (Apache 2.0).  
> Part of the **H:\Automation** content pipeline — Step 3 of 4.

---

## What It Does

LocalTTS converts any text into broadcast-quality speech audio (24 kHz mono WAV).  
It integrates with the pipeline's [Project Folder Contract](../PROJECT_FOLDER_CONTRACT.md):

- **Input:** `script.txt` → reads from project folders
- **Output:** `audio.wav` → writes directly into the project folder
- **Voice matching:** reads `metadata.json → preset_name` and auto-selects the best voice

Runs entirely **offline** after the first-time model download (~316 MB).  
No API keys, no cloud, no usage limits.

---

## Quick Start

```bat
cd H:\Automation\TTS
run.bat
```

`run.bat` locates your Python installation automatically (uv → py launcher → python).  
The startup dialog installs missing packages and downloads the model on first run.

**Manual launch:**
```bat
python main.py
```

---

## Features

| Feature | Details |
|---|---|
| **TTS engine** | Kokoro-82M via `kokoro-onnx` (ONNX Runtime, CPU-only) |
| **Voices** | 18 voices — 7 American Female, 5 American Male, 3 British Female, 3 British Male |
| **Sample rate** | 24 000 Hz mono WAV |
| **Long text** | Auto-chunked at sentence boundaries, merged seamlessly |
| **Queue** | Multi-job worker thread with pause / resume / retry |
| **Project folders** | Universal multi-folder picker — select any number of project folders at once |
| **Batch files** | Load multiple `.txt` files; queue all in one click |
| **History** | Per-session log of completed jobs; exportable to CSV |
| **Console** | Live scrolling log viewer with level filtering |
| **Settings** | Persistent via `~/.config/localtts/settings.json` |

---

## UI Pages

```
🎤 Synthesize  – type/paste text or load files; pick voice & speed; add to queue
📋 Queue       – live job list with progress, Play, Open Folder, Retry, Cancel
🎙 Voices      – browse all 18 voices by gender; search by name or description
📜 History     – completed-job log with playback and CSV export
🖥 Console     – full live app log with DEBUG/INFO/STEP/WARN/ERROR filtering
⚙ Settings   – output folder, filename template, defaults, behaviour flags
```

---

## Project Folder Integration

When "📁 Add Project Folders…" is clicked on the **Synthesize → Multi-File** tab,
the **Universal Folder Selector** opens — a custom tree-view dialog that lets you:

1. Navigate the filesystem tree panel on the left
2. Select any number of folders by clicking **✚ Add to Selection**
3. Confirm — each folder is validated and queued automatically

For each folder the tool:
- Checks for `script.txt` (skips the folder if missing)
- Reads `metadata.json → preset_name` and matches it to the closest voice
- Sets output to `<project_folder>/audio.wav` per the pipeline contract

---

## Voice Catalogue

| ID | Name | Accent | Gender | Best For |
|---|---|---|---|---|
| `af_heart` | Heart | American | Female | Storytelling, vlogs |
| `af_bella` | Bella | American | Female | Social media |
| `af_sarah` | Sarah | American | Female | Podcasts, presentations |
| `af_sky` | Sky | American | Female | Ads, promos |
| `af_nicole` | Nicole | American | Female | Meditation, narration |
| `af_aoede` | Aoede | American | Female | Audiobooks |
| `af_kore` | Kore | American | Female | YouTube Shorts |
| `am_adam` | Adam | American | Male | News, documentaries |
| `am_michael` | Michael | American | Male | Podcasts, tutorials |
| `am_fenrir` | Fenrir | American | Male | Trailers, promos |
| `am_puck` | Puck | American | Male | Gaming, entertainment |
| `am_echo` | Echo | American | Male | Explainers, tutorials |
| `bf_emma` | Emma | British | Female | Luxury, lifestyle |
| `bf_isabella` | Isabella | British | Female | Brand narration |
| `bf_alice` | Alice | British | Female | News, education |
| `bm_george` | George | British | Male | Docs, corporate |
| `bm_lewis` | Lewis | British | Male | Social media |
| `bm_daniel` | Daniel | British | Male | Narration, audiobooks |

---

## File & Folder Structure

```
TTS/
├── main.py                  # Entry point — launches the Tkinter GUI
├── run.bat                  # Windows double-click launcher
├── requirements.txt         # Python dependencies
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Voice catalogue, model paths, config persistence
│
├── core/
│   ├── __init__.py
│   ├── logger.py            # Thread-safe logging hub with subscriber pattern
│   ├── model_manager.py     # Downloads & caches Kokoro model files
│   ├── tts_backend.py       # Kokoro engine: chunking, synthesis, WAV merge
│   ├── file_handler.py      # File I/O, output path builder
│   └── queue_manager.py     # Job queue: pause/resume/retry, worker thread
│
└── ui/
    ├── __init__.py
    ├── theme.py             # Dark colour palette & ttk.Style config
    ├── dep_check.py         # Startup dialog: auto-install packages + models
    ├── folder_picker.py     # Universal multi-folder selector dialog
    └── app.py               # Main application: 6-page Tkinter GUI
```

---

## Configuration

Settings are stored in `~/.config/localtts/settings.json`.

| Key | Default | Description |
|---|---|---|
| `output_dir` | `~/tts_output` | Where standalone WAV files are saved |
| `voice` | `Heart · American Female` | Default voice |
| `speed` | `1.0` | Speech speed (0.5× – 2.0×) |
| `chunk_limit` | `300` | Max characters per synthesis chunk |
| `auto_open_output` | `false` | Open output folder on job completion |
| `auto_clear_done` | `false` | Auto-remove completed jobs from queue |
| `show_notifications` | `true` | Toast popups on job completion |
| `output_template` | `{name}_{ts}` | Filename template (`{name}`, `{ts}`, `{voice}`, `{speed}`) |

---

## Model Files

Downloaded once on first run to `~/.config/localtts/models/`:

| File | Size | Purpose |
|---|---|---|
| `kokoro-v1.0.onnx` | ~310 MB | Neural TTS network weights |
| `voices-v1.0.bin` | ~6 MB | Voice embeddings for all 18 speakers |

Source: [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)  
Licence: Apache 2.0

---

## Requirements

- **Python** 3.10 – 3.13 (64-bit)
- **OS:** Windows 10/11 (primary), macOS, Linux
- **RAM:** 1 GB free (model is loaded once and kept in memory)
- **Disk:** ~320 MB for model cache

Python packages (auto-installed by the startup dialog):
```
kokoro-onnx
onnxruntime
soundfile
numpy
espeakng-loader
phonemizer-fork
requests
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` | Add current text/files to queue |
| `Ctrl+L` | Load file(s) dialog |

---

## Pipeline Position

```
Content Automation  →  Image Automation  →  TTS  →  Video Forge
      (Step 1)              (Step 2)         (Step 3)   (Step 4)
   script.txt                                audio.wav
   metadata.json         ──────────────────►
```

See [PROJECT_FOLDER_CONTRACT.md](../PROJECT_FOLDER_CONTRACT.md) for the full pipeline specification.
