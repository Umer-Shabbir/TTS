# LocalTTS — Architecture Notes

## Overview

LocalTTS is a self-contained Tkinter desktop application built around a
CPU-only neural TTS engine (Kokoro-82M). The architecture is deliberately
simple and flat — no framework, no DI container, no async — just stdlib
threading and a pub/sub event bus.

---

## Module Dependency Graph

```
main.py
 └── ui/dep_check.py          (startup dialog)
      └── ui/app.py            (full GUI)
           ├── config/settings.py
           ├── core/queue_manager.py
           │    └── core/tts_backend.py
           │         └── config/settings.py
           ├── core/file_handler.py
           ├── core/logger.py
           ├── ui/theme.py
           └── ui/folder_picker.py
```

---

## Layer Breakdown

### `config/settings.py`
Pure data — no side effects beyond creating the config directory.

- `VOICE_CATALOGUE`: the 18 Kokoro voice definitions
- `load()` / `save()`: JSON-based settings persistence to `~/.config/localtts/settings.json`
- `MODEL_DIR`, `MODEL_FILE`, `VOICES_FILE`: canonical paths used by every other module

### `core/logger.py`
Thread-safe singleton `AppLogger` (the global `log`).

- In-memory ring buffer of the last 2000 entries
- File output to `~/.config/localtts/app.log`
- Subscriber pattern: the Console page calls `log.subscribe()` and receives
  live entries on whatever thread they're logged from; it dispatches to the UI
  thread via `root.after(0, ...)`.

### `core/model_manager.py`
Downloads the two Kokoro model files on first run using `urllib.request` with
a 64 KB streaming buffer and `.tmp` rename-on-success safety.

### `core/tts_backend.py`
`TTSEngine` — holds lazily-loaded engine instances (Kokoro ONNX, Piper ONNX, and Edge-TTS).

- `chunk_text()`: sentence-aligned chunking at ≤ N characters
- `concat_wavs()`: stdlib `wave` merge with no extra dependencies
- `synthesize()`: dynamically dispatches synthesis to Kokoro, Piper (offline ONNX), or Edge-TTS (online streaming API) based on voice configuration. Auto-chunks long text; writes temp WAVs per chunk, merges, cleans up regardless of exceptions.

The engine is **owned by the worker thread** — it is not thread-safe and is
never touched from the UI thread.

### `core/queue_manager.py`
`QueueManager` wraps a `queue.Queue` with pause/resume/retry semantics.

- A single daemon worker thread polls the queue with a 0.5 s timeout loop
- Pause is implemented via `threading.Event` (`_resume`): the worker blocks
  after completing a job when the event is cleared
- All callbacks are dispatched via `schedule_fn` (= `root.after(0, fn)`) so
  the UI always receives events on the main thread
- Retry creates a new `TTSJob` cloning the failed job's parameters

### `ui/theme.py`
Stateless colour tokens and `apply(root)` which configures `ttk.Style`.
Nothing else imports from here except `ui/`.

### `ui/dep_check.py`
`StartupDialog` — shown before the main window is revealed.

- Phase 1: scans installed packages via `importlib.util.find_spec`
- Phase 2: checks model file sizes; downloads if stale
- Phase 3: auto-launches after all checks pass (or after 0.9 s delay on success)

All heavy work runs in daemon threads; the Tkinter event loop stays responsive.

### `ui/folder_picker.py`
`_FolderPickerDialog` — custom multi-folder selector modal.

- Left panel: `ttk.Treeview` filesystem browser (drives on Windows, `/` on POSIX)
- Lazy expansion: subdirectory children are scanned only when a node is expanded
- Right panel: `tk.Listbox` of confirmed selections
- Returns `list[Path]` via `ask_folders()` public API

This replaces Tkinter's `filedialog.askdirectory()` which can only pick
one folder at a time.

### `ui/app.py`
All six pages (Synthesize, Queue, Voices, History, Console, Settings)
plus helpers (Sidebar, JobCard, VoiceCard, Toast, ScrollFrame, Tooltip).

The top-level `App` class:
1. Creates `QueueManager` and wires all event callbacks
2. Instantiates all pages, keeps them hidden; shows one at a time via `pack/pack_forget`
3. Routes `QueueManager` events to the `QueuePage` and `HistoryPage`

---

## Threading Model

```
Main thread (Tkinter event loop)
  ├── All UI interaction
  ├── All queue event callbacks (dispatched via root.after)
  └── Startup dialog phases 1-3 (daemon threads → root.after callbacks)

tts-worker (daemon thread)
  ├── Polls queue.Queue
  ├── Calls TTSEngine.synthesize() (blocks until complete)
  └── Emits events via QueueManager._emit → schedule_fn → root.after
```

The TTS engine is **only ever called from the tts-worker thread**.  
The UI thread **never** touches numpy arrays or ONNX sessions.

---

## Data Flow: Project Folder → audio.wav

```
User clicks "📁 Add Project Folders…"
  └── ask_folders() shows FolderPickerDialog
       └── User confirms N folders
            └── SynthesizePage._load_project_folders_dialog()
                 For each folder:
                   1. Read  <folder>/script.txt          (required)
                   2. Read  <folder>/metadata.json       (optional)
                   3. Match preset_name → voice catalogue
                   4. Create TTSJob(output_path=<folder>/audio.wav)
                   5. QueueManager.enqueue(job)
                        └── worker thread picks up job
                             └── TTSEngine.synthesize(text, out_path, voice)
                                  └── chunk_text() → synthesize chunks → concat_wavs()
                                       └── audio.wav written to project folder
```

---

## Configuration Persistence

`config/settings.py::save(cfg)` writes the full settings dict as pretty JSON to
`~/.config/localtts/settings.json` on every change (voice, speed, output dir,
template, boolean flags). This is intentional — the cost of a few JSON writes
is negligible and the settings are always up to date if the app crashes.

---

## Known Limitations

| Limitation | Reason / Workaround |
|---|---|
| CPU-only synthesis | Kokoro-onnx ships CPU ONNX only; a GPU provider could be added via `onnxruntime-gpu` + session options |
| Single worker thread | One job at a time; adding concurrency would require multiple `TTSEngine` instances (each ~1 GB RAM) |
| No subtitle/SRT output | Out of scope for this tool — Video Forge handles subtitle alignment from `script.txt` |
| Tkinter only | No web or REST interface; intentional (zero-dependency desktop app) |
