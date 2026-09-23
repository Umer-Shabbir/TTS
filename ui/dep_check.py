"""
ui/dep_check.py – Three-phase startup dialog for Kokoro TTS backend.

Phase 1 – Install Python packages (kokoro-onnx, onnxruntime, soundfile, …)
Phase 2 – Download Kokoro model files (kokoro-v1.0.onnx + voices-v1.0.bin)
Phase 3 – Auto-launch

All heavy work runs in daemon threads; the UI stays fully responsive.
"""
import importlib.util
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

BG      = "#0d0d1a"
CARD    = "#1a1a35"
BORDER  = "#252545"
TEXT    = "#e8e8ff"
TEXT2   = "#8080b0"
ACCENT  = "#6c47f5"
SUCCESS = "#2ecc71"
ERROR   = "#e05050"
WARNING = "#f0a030"

# ── Complete dependency manifest ─────────────────────────────────────────────
# (name for display, import probe, pip install args)
DEPS = [
    ("kokoro-onnx",    "kokoro_onnx", ["kokoro-onnx"]),
    ("onnxruntime",    "onnxruntime", ["onnxruntime"]),
    ("soundfile",      "soundfile",   ["soundfile"]),
    ("numpy",          "numpy",       ["numpy"]),
    ("espeakng-loader","espeakng_loader", ["espeakng-loader"]),
    ("phonemizer-fork","phonemizer",  ["phonemizer-fork"]),
    ("requests",       "requests",    ["requests"]),
]

PHASES = [
    {
        "key":    "packages",
        "title":  "Python Packages",
        "detail": "kokoro-onnx · onnxruntime · soundfile · numpy · phonemizer",
    },
    {
        "key":    "model",
        "title":  "Kokoro Voice Model",
        "detail": "Kokoro-82M  ·  voices-v1.0.bin + kokoro-v1.0.onnx  ·  ~316 MB total  (once only)",
    },
]


class StartupDialog:
    def __init__(self, root: tk.Tk, on_ready: Callable):
        self._root   = root
        self._cb     = on_ready
        self._rows   = {}
        self._missing: list[tuple] = []
        self._install_q: list[tuple] = []
        self._cur    = None

        from ui.theme import apply
        apply(root)

        self._w = tk.Toplevel(root)
        self._w.title("LocalTTS – Starting Up")
        self._w.configure(bg=BG)
        self._w.resizable(False, False)
        self._w.protocol("WM_DELETE_WINDOW", self._quit)
        self._build()
        self._center()
        self._w.after(200, self._phase1_check)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self._w, bg=BG)
        outer.pack(fill="both", expand=True)

        # Coloured header
        hdr = tk.Frame(outer, bg=ACCENT, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔊  LocalTTS", bg=ACCENT, fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=22)
        tk.Label(hdr, text="v3.1 · Kokoro TTS", bg=ACCENT, fg="#c0b0ff",
                 font=("Segoe UI", 10)).pack(side="right", padx=22, pady=(4, 0))

        body = tk.Frame(outer, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=14)

        tk.Label(body, text="Checking requirements before launch…",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12))

        # Phase rows
        for ph in PHASES:
            self._rows[ph["key"]] = self._make_phase_row(body, ph)

        # Log area
        lf = tk.Frame(body, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        lf.pack(fill="x", pady=(12, 0))
        self._log = tk.Text(lf, height=9, bg=CARD, fg=TEXT2,
                             font=("Consolas", 9), relief="flat", bd=0,
                             state="disabled", wrap="word")
        sb = ttk.Scrollbar(lf, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        sb.pack(side="right", fill="y", pady=2)

        # Banner
        self._banner_v = tk.StringVar(value="Checking packages…")
        self._banner   = tk.Label(body, textvariable=self._banner_v,
                                  bg=BG, fg=WARNING, font=("Segoe UI", 10),
                                  wraplength=555, anchor="w")
        self._banner.pack(fill="x", pady=(10, 0))

        # Buttons
        bf = tk.Frame(body, bg=BG)
        bf.pack(fill="x", pady=(10, 2))
        self._btn_quit = tk.Button(
            bf, text="Quit", bg=CARD, fg=TEXT, relief="flat",
            font=("Segoe UI", 10), padx=14, pady=7,
            activebackground=BORDER, cursor="hand2", command=self._quit)
        self._btn_quit.pack(side="right", padx=(8, 0))
        self._btn_install = tk.Button(
            bf, text="⬇  Install Missing Packages", bg=ACCENT, fg="white",
            relief="flat", font=("Segoe UI", 10, "bold"),
            padx=14, pady=7, activebackground="#8b6fff",
            cursor="hand2", command=self._phase1_install)
        self._btn_launch = tk.Button(
            bf, text="🚀  Launch LocalTTS", bg=SUCCESS, fg="#051a10",
            relief="flat", font=("Segoe UI", 10, "bold"),
            padx=20, pady=7, activebackground="#4edd8a",
            cursor="hand2", command=self._launch)

        self._w.geometry("640x600")

    def _make_phase_row(self, parent, ph: dict) -> dict:
        f = tk.Frame(parent, bg=CARD, padx=14, pady=10,
                     highlightthickness=1, highlightbackground=BORDER)
        f.pack(fill="x", pady=3)
        f.columnconfigure(1, weight=1)
        icon_v = tk.StringVar(value="⬜")
        icon_l = tk.Label(f, textvariable=icon_v, bg=CARD, fg=TEXT2,
                          font=("Segoe UI", 14), width=2, anchor="center")
        icon_l.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 10))
        tk.Label(f, text=ph["title"], bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), anchor="w").grid(
                     row=0, column=1, sticky="ew")
        note_v = tk.StringVar(value=ph["detail"])
        note_l = tk.Label(f, textvariable=note_v, bg=CARD, fg=TEXT2,
                          font=("Segoe UI", 9), anchor="w")
        note_l.grid(row=1, column=1, sticky="ew")
        prog = ttk.Progressbar(f, mode="indeterminate", length=200)
        return {"icon_v": icon_v, "icon_l": icon_l,
                "note_v": note_v, "note_l": note_l,
                "prog": prog, "frame": f}

    # ── Phase 1: Packages ─────────────────────────────────────────────────────

    def _phase1_check(self):
        self._set_row("packages", "⟳", ACCENT, "Checking…")
        self._log_w("Checking installed packages…\n", TEXT2)
        missing = []
        for name, imp, pip_args in DEPS:
            ok = importlib.util.find_spec(imp) is not None
            self._log_w(f"  {'✓' if ok else '✗':3s}  {name}\n",
                        SUCCESS if ok else WARNING)
            if not ok:
                missing.append((name, imp, pip_args))
        self._missing = missing

        if not missing:
            self._log_w("\nAll packages present.\n", SUCCESS)
            self._set_row("packages", "✓", SUCCESS, "All packages installed ✓")
            self._w.after(300, self._phase2_check)
        else:
            names = ", ".join(n for n, _, _ in missing)
            self._set_row("packages", "✗", ERROR, f"Missing: {names}")
            self._banner_v.set(
                f"{len(missing)} package(s) missing — click Install to continue.")
            self._banner.configure(fg=WARNING)
            self._btn_install.pack(side="right")

    def _phase1_install(self):
        self._btn_install.configure(state="disabled")
        self._btn_quit.configure(state="disabled")
        self._banner_v.set("Installing packages…")
        self._banner.configure(fg=ACCENT)
        # Build deduped install queue
        seen: set[tuple] = set()
        self._install_q = []
        for name, imp, pip_args in self._missing:
            key = tuple(pip_args)
            if key not in seen:
                seen.add(key)
                self._install_q.append((name, imp, pip_args))
        self._run_next_pkg()

    def _run_next_pkg(self):
        if not self._install_q:
            self._verify_pkgs(); return
        name, imp, pip_args = self._install_q.pop(0)
        self._cur = (name, imp, pip_args)
        self._set_row("packages", "⟳", ACCENT, f"Installing {name}…")

        args = [sys.executable, "-m", "pip", "install", "--upgrade"] + pip_args

        # In modern Python, tools like `uv` create PEP 668 externally-managed environments.
        # For our lightweight GUI install flow, we safely override this constraint
        # so the app can auto-bootstrap its own packages into whatever python environment it was launched with.
        args.append("--break-system-packages")

        self._log_w(f"\n$ {' '.join(args)}\n", ACCENT)

        def _run():
            try:
                p = subprocess.Popen(args, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
                for ln in p.stdout:
                    self._w.after(0, lambda l=ln: self._log_w(l))
                p.wait(); code = p.returncode
            except Exception as e:
                code = -1
                self._w.after(0, lambda: self._log_w(f"Error: {e}\n", ERROR))
            self._w.after(0, lambda c=code: self._pkg_done(c))

        threading.Thread(target=_run, daemon=True).start()

    def _pkg_done(self, code: int):
        if code == 0: self._log_w("  ✓ Done\n", SUCCESS)
        else:         self._log_w(f"  ✗ Exit {code}\n", ERROR)
        self._run_next_pkg()

    def _verify_pkgs(self):
        self._log_w("\nVerifying…\n", TEXT2)
        still = []
        for name, imp, _ in DEPS:
            ok = importlib.util.find_spec(imp) is not None
            self._log_w(f"  {'✓' if ok else '✗'}  {name}\n",
                        SUCCESS if ok else ERROR)
            if not ok: still.append(name)
        if still:
            self._set_row("packages", "✗", ERROR,
                          f"Still missing: {', '.join(still)}")
            self._banner_v.set("⚠ Some packages failed. Check the log and retry.")
            self._banner.configure(fg=ERROR)
            self._btn_install.configure(state="normal", text="⟳  Retry Install")
            self._btn_install.pack(side="right")
            self._btn_quit.configure(state="normal")
        else:
            self._set_row("packages", "✓", SUCCESS, "All packages installed ✓")
            self._log_w("✓ All packages verified.\n", SUCCESS)
            self._btn_quit.configure(state="normal")
            self._w.after(300, self._phase2_check)

    # ── Phase 2: Model download ───────────────────────────────────────────────

    def _phase2_check(self):
        self._set_row("model", "⟳", ACCENT, "Checking model cache…")
        self._log_w("\nChecking Kokoro model files…\n", TEXT2)

        def _check():
            try:
                from core.model_manager import models_cached
                cached = models_cached()
            except Exception as e:
                self._w.after(0, lambda: self._log_w(f"  Error: {e}\n", WARNING))
                cached = False
            self._w.after(0, lambda: self._phase2_result(cached))

        threading.Thread(target=_check, daemon=True).start()

    def _phase2_result(self, cached: bool):
        if cached:
            self._set_row("model", "✓", SUCCESS, "Model files cached ✓")
            self._log_w("  All model files present — skipping download.\n", SUCCESS)
            self._all_done(); return

        self._set_row("model", "⟳", ACCENT,
                      "Downloading kokoro-v1.0.onnx + voices-v1.0.bin (~316 MB)…")
        row = self._rows["model"]
        row["prog"].grid(row=2, column=1, sticky="w", pady=(6, 0))
        row["prog"].start(12)
        self._log_w("  Downloading Kokoro model files (~316 MB total)…\n", WARNING)
        self._banner_v.set(
            "Downloading Kokoro-82M model files (~316 MB).\n"
            "This happens once — all future launches will be instant.")
        self._banner.configure(fg=WARNING)

        def _dl():
            try:
                from core.model_manager import ensure_models_downloaded
                ok, err = ensure_models_downloaded(
                    progress_cb=lambda m: self._w.after(
                        0, lambda msg=m: self._log_w(f"  {msg}\n")))
            except Exception as e:
                ok, err = False, str(e)
                self._w.after(0, lambda: self._log_w(f"  Error: {e}\n", ERROR))
            self._w.after(0, lambda: self._model_done(ok, err))

        threading.Thread(target=_dl, daemon=True).start()

    def _model_done(self, ok: bool, err: str):
        row = self._rows["model"]
        row["prog"].stop(); row["prog"].grid_forget()
        if ok:
            self._set_row("model", "✓", SUCCESS, "Model files ready ✓")
            self._log_w("  ✓ Download complete.\n", SUCCESS)
            self._all_done()
        else:
            self._set_row("model", "✗", ERROR,
                          f"Download failed: {err[:60]}")
            self._log_w(f"  ✗ {err}\n", ERROR)
            self._log_w(
                "\nYou can retry the download, or manually place the files in:\n"
                f"  {__import__('config.settings', fromlist=['MODEL_DIR']).MODEL_DIR}\n\n"
                "Files needed:\n"
                "  kokoro-v1.0.onnx  (from github.com/thewh1teagle/kokoro-onnx/releases)\n"
                "  voices-v1.0.bin\n",
                WARNING)
            # Still allow launch — engine will give a clear error on first job
            self._all_done()

    # ── Phase 3: Launch ───────────────────────────────────────────────────────

    def _all_done(self):
        self._banner_v.set("✓  Ready to launch!")
        self._banner.configure(fg=SUCCESS)
        self._btn_launch.pack(side="right")
        self._log_w("\nAll done — launching LocalTTS…\n", SUCCESS)
        self._w.after(900, self._launch)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_row(self, key: str, icon: str, color: str, note: str = ""):
        def _do():
            r = self._rows[key]
            r["icon_v"].set(icon); r["icon_l"].configure(fg=color)
            if note: r["note_v"].set(note); r["note_l"].configure(fg=color)
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self._w.after(0, _do)

    def _log_w(self, text: str, color: str | None = None):
        def _do():
            self._log.configure(state="normal")
            if color:
                tag = f"c{color[1:]}"
                self._log.tag_configure(tag, foreground=color)
                self._log.insert("end", text, tag)
            else:
                self._log.insert("end", text)
            self._log.see("end")
            self._log.configure(state="disabled")
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self._w.after(0, _do)

    def _center(self):
        self._w.update_idletasks()
        w, h = self._w.winfo_reqwidth(), self._w.winfo_reqheight()
        sw, sh = self._w.winfo_screenwidth(), self._w.winfo_screenheight()
        self._w.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _launch(self): self._w.destroy(); self._cb()

    def _quit(self):
        self._root.quit(); self._root.destroy(); sys.exit(0)
