# LocalTTS — Changelog

All notable changes to LocalTTS are documented here.

---

## v3.1  (current)

### Added
- **Universal multi-folder selector** (`ui/folder_picker.py`)
  - Custom `Toplevel` dialog with a full filesystem tree-view (drives on Windows, `/` on POSIX)
  - Lazy directory expansion — subdirectory children are only scanned on demand
  - Select **any number of project folders** in one operation; confirm with a single click
  - Replaces the broken `filedialog.askopenfilenames()` workaround which required selecting files *inside* a folder
  - Address bar shows the currently focused path
  - Selection list on the right with per-item remove and Clear All

- **Documentation suite**
  - `README.md` — feature overview, quick start, voice catalogue, configuration reference
  - `ARCHITECTURE.md` — module dependency graph, threading model, data flow diagram
  - `CHANGELOG.md` — this file

### Fixed
- **Duplicate `_load_project_folders_dialog`** in `SynthesizePage` — the dead first
  definition (used `askdirectory` for a single folder) was shadowing the second; both
  have been removed and replaced with a single correct implementation using the new
  universal folder picker

- **Duplicate `on_cancelled`** in `QueuePage` — the second identical definition that
  silently overwrote the first has been removed

### Changed
- `_load_project_folders_dialog` now directly enqueues jobs to the queue (no intermediate
  staging in `_file_list`), which means the project folder workflow always navigates to the
  Queue page on success — consistent with how the single-folder path worked previously

- Skipped folders (missing `script.txt` or empty content) are now counted and reported in
  the status bar message alongside the success count

---

## v3.0

### Added
- 18-voice Kokoro-82M catalogue (7 American Female, 5 American Male, 3 British Female, 3 British Male)
- Six-page GUI: Synthesize, Queue, Voices, History, Console, Settings
- Multi-file batch loading (Files tab)
- Project folder support — reads `script.txt`, matches `metadata.json → preset_name` to a voice
- Pause / Resume / Retry queue control
- Toast notifications on job completion
- CSV export from History page
- Live Console page with level filtering and Pause Scroll
- Persistent settings (`~/.config/localtts/settings.json`)
- Filename template with `{name}`, `{ts}`, `{voice}`, `{speed}` variables
- Three-phase startup dialog: package install → model download → auto-launch
- `run.bat` for Windows double-click launch with Python auto-detection

### Technical
- Kokoro engine loaded lazily (on first synthesis, not on startup)
- Sentence-aligned text chunking at ≤ 300 chars per chunk
- Stdlib `wave` merge — no extra dependencies for WAV concatenation
- All queue event callbacks dispatched to UI thread via `root.after(0, fn)`
- Model files downloaded with streaming 64 KB blocks and `.tmp` rename-on-success

---

## v2.x  (previous generation — Silero backend)

> Replaced in v3.0. Silero VITS was superseded by Kokoro-82M for significantly
> higher audio quality, especially for social media and narration use cases.
