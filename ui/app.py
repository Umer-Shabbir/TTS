"""
ui/app.py – LocalTTS v3 complete application.

Pages:    Synthesize | Queue | Voices | History | Settings
Features: multi-file, pause/resume, retry, play audio, voice search,
          toast notifications, keyboard shortcuts, auto-open, timing, etc.
"""
import os, subprocess, sys, time, tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

import config.settings as CFG
from config.settings import VOICE_CATALOGUE, APP_VERSION
from core.file_handler import build_output_path, load_multiple_files, read_text_file
from core.queue_manager import QueueManager, TTSJob
from core.logger import log
from ui.folder_picker import ask_folders
from ui.theme import (
    BG, SURFACE, CARD, CARD_HVR, CARD_ACT, BORDER, BORDER2,
    TEXT, TEXT2, TEXT3, ACCENT, ACCENT_L, ACCENT_D, ACCENT_BG,
    SUCCESS, SUCCESS_B, SUCCESS_L,
    WARNING, WARNING_B, WARNING_L,
    ERROR, ERROR_B, ERROR_L,
    INFO, INFO_B, PAUSED_C, PAUSED_B, NEUTRAL_B,
    FEMALE_BG, FEMALE_ACC, MALE_BG, MALE_ACC, NEUTRAL_BG, NEUTRAL_ACC,
    F_SMALL, F_NORMAL, F_BOLD, F_TITLE, F_H1, F_H2, F_MONO, F_BADGE, F_LABEL,
    apply,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Utility widgets & helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _open_path(path: str):
    """Open a file or folder with the OS default handler."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _btn(parent, text, cmd, bg=ACCENT, fg="white", font=F_BOLD,
         padx=14, pady=7, hover=None, active_bg=None, width=None, cursor="hand2") -> tk.Button:
    if hover is None:     hover     = ACCENT_L
    if active_bg is None: active_bg = hover
    kw = dict(bg=bg, fg=fg, text=text, relief="flat", font=font,
              padx=padx, pady=pady, activebackground=active_bg,
              activeforeground=fg, cursor=cursor, command=cmd, bd=0)
    if width:
        kw["width"] = width
    b = tk.Button(parent, **kw)
    def _on_enter(e, _b=b, _h=hover):
        if str(_b.cget("state")) != "disabled":
            _b.configure(bg=_h)
    def _on_leave(e, _b=b, _bg=bg):
        if str(_b.cget("state")) != "disabled":
            _b.configure(bg=_bg)
    b.bind("<Enter>", _on_enter)
    b.bind("<Leave>", _on_leave)
    return b


def _sep(parent, bg=BORDER, height=1):
    return tk.Frame(parent, bg=bg, height=height)


def _lbl(parent, text, fg=TEXT, bg=BG, font=F_NORMAL, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=font, **kw)


class Tooltip:
    """Simple hover tooltip."""
    def __init__(self, widget, text: str):
        self._w, self._text, self._tip = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, e):
        x = self._w.winfo_rootx() + 20
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=BORDER2)
        tk.Label(tw, text=self._text, bg=CARD, fg=TEXT2,
                 font=("Segoe UI", 9), padx=8, pady=4,
                 relief="flat").pack()

    def _hide(self, e):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ScrollFrame(tk.Frame):
    """Vertically scrollable container. Scroll binds only when mouse is inside."""
    def __init__(self, parent, bg=BG, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb    = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner  = tk.Frame(self.canvas, bg=bg)
        self._cwin  = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self._cwin, width=e.width))
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, e):
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", self._wheel_linux)
        self.canvas.bind_all("<Button-5>", self._wheel_linux)

    def _unbind_mousewheel(self, e):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _wheel(self, e):
        # macOS returns small delta, Windows typically -120 or 120
        delta = e.delta
        if sys.platform == "darwin":
            self.canvas.yview_scroll(int(-1 * delta), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _wheel_linux(self, e):
        if e.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif e.num == 5:
            self.canvas.yview_scroll(1, "units")

    def scroll_bottom(self):
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def scroll_to(self, widget):
        self.canvas.update_idletasks()
        try:
            y = widget.winfo_y()
            h = self.canvas.winfo_height()
            total = self.inner.winfo_reqheight()
            if total > 0:
                self.canvas.yview_moveto(max(0, (y - h // 3) / total))
        except Exception:
            pass


class Toast:
    """Transient notification that fades after a few seconds."""
    def __init__(self, root: tk.Tk, message: str,
                 bg=SUCCESS_B, fg=SUCCESS_L, duration=3200):
        self._root = root
        tw = tk.Toplevel(root)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        # Position: bottom-right of main window
        root.update_idletasks()
        rx = root.winfo_x() + root.winfo_width()
        ry = root.winfo_y() + root.winfo_height()
        f = tk.Frame(tw, bg=bg, padx=14, pady=10,
                     highlightthickness=1, highlightbackground=BORDER2)
        f.pack()
        tk.Label(f, text=message, bg=bg, fg=fg,
                 font=("Segoe UI", 10), wraplength=280).pack()
        tw.update_idletasks()
        w = tw.winfo_reqwidth(); h = tw.winfo_reqheight()
        tw.wm_geometry(f"+{rx - w - 20}+{ry - h - 40}")
        root.after(duration, tw.destroy)


# ═══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ═══════════════════════════════════════════════════════════════════════════════

_NAV = [
    ("synthesize", "🎤", "Synthesize"),
    ("queue",      "📋", "Queue"),
    ("voices",     "🎙", "Voices"),
    ("history",    "📜", "History"),
    ("console",    "🖥",  "Console"),
    ("settings",   "⚙",  "Settings"),
]

class Sidebar(tk.Frame):
    def __init__(self, parent, on_select: Callable, **kw):
        super().__init__(parent, bg=SURFACE, width=168, **kw)
        self.pack_propagate(False)
        self._on_select  = on_select
        self._items: dict = {}
        self._badges: dict[str, tk.Label] = {}
        self._active = ""

        # ── Logo ─────────────────────────────────────────────────────
        logo = tk.Frame(self, bg=SURFACE)
        logo.pack(fill="x", pady=(20, 0))
        tk.Label(logo, text="🔊", bg=SURFACE, fg=ACCENT,
                 font=("Segoe UI", 22)).pack(side="left", padx=(14, 6))
        lv = tk.Frame(logo, bg=SURFACE)
        lv.pack(side="left")
        tk.Label(lv, text="LocalTTS", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(lv, text=f"v{APP_VERSION}", bg=SURFACE, fg=TEXT3,
                 font=("Segoe UI", 8)).pack(anchor="w")

        _sep(self, BORDER).pack(fill="x", padx=12, pady=14)

        for key, icon, label in _NAV:
            self._make_item(key, icon, label)

        # ── Queue status indicator ────────────────────────────────────
        _sep(self, BORDER).pack(fill="x", padx=12, pady=8)
        self._status_frame = tk.Frame(self, bg=SURFACE, padx=14, pady=6)
        self._status_frame.pack(fill="x")
        self._status_dot = tk.Label(self._status_frame, text="●", bg=SURFACE,
                                    fg=TEXT3, font=("Segoe UI", 8))
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(self._status_frame, text="Idle",
                                    bg=SURFACE, fg=TEXT3, font=("Segoe UI", 8))
        self._status_lbl.pack(side="left", padx=(4, 0))

    def _make_item(self, key: str, icon: str, label: str):
        row   = tk.Frame(self, bg=SURFACE, cursor="hand2")
        row.pack(fill="x", padx=6, pady=1)
        bar   = tk.Frame(row, bg=SURFACE, width=3)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(row, bg=SURFACE, padx=10, pady=9)
        inner.pack(side="left", fill="x", expand=True)
        il    = tk.Label(inner, text=icon, bg=SURFACE, fg=TEXT2,
                         font=("Segoe UI", 13))
        il.pack(side="left", padx=(0, 8))
        ll    = tk.Label(inner, text=label, bg=SURFACE, fg=TEXT2,
                         font=("Segoe UI", 10))
        ll.pack(side="left")
        badge = tk.Label(inner, text="", bg=ACCENT, fg="white",
                         font=("Segoe UI", 8, "bold"), padx=5, pady=1)
        self._badges[key] = badge

        def _click(e, k=key): self.select(k)
        for w in (row, inner, il, ll, bar):
            w.bind("<Button-1>", _click)
            w.bind("<Enter>",
                   lambda e, r=row, i=inner, b=bar:
                   [r.configure(bg=CARD_HVR), i.configure(bg=CARD_HVR),
                    b.configure(bg=BORDER)] if key != self._active else None)
            w.bind("<Leave>",
                   lambda e, r=row, i=inner, b=bar:
                   [r.configure(bg=SURFACE if key != self._active else CARD_HVR),
                    i.configure(bg=SURFACE if key != self._active else CARD_HVR),
                    b.configure(bg=SURFACE if key != self._active else ACCENT)] )
        self._items[key] = {"row": row, "bar": bar, "inner": inner,
                             "il": il, "ll": ll}

    def select(self, key: str):
        if self._active and self._active in self._items:
            old = self._items[self._active]
            for w in ("row", "inner"): old[w].configure(bg=SURFACE)
            old["bar"].configure(bg=SURFACE)
            old["il"].configure(bg=SURFACE, fg=TEXT2)
            old["ll"].configure(bg=SURFACE, fg=TEXT2)
        self._active = key
        it = self._items[key]
        for w in ("row", "inner"): it[w].configure(bg=CARD_HVR)
        it["bar"].configure(bg=ACCENT)
        it["il"].configure(bg=CARD_HVR, fg=ACCENT)
        it["ll"].configure(bg=CARD_HVR, fg=TEXT)
        self._on_select(key)

    def set_badge(self, key: str, count: int):
        b = self._badges.get(key)
        if not b: return
        if count > 0:
            b.configure(text=str(count))
            b.pack(side="right")
        else:
            b.pack_forget()

    def set_engine_status(self, status: str, color: str):
        self._status_dot.configure(fg=color)
        self._status_lbl.configure(text=status, fg=color)


# ═══════════════════════════════════════════════════════════════════════════════
#  Job Card  (Queue page)
# ═══════════════════════════════════════════════════════════════════════════════

_STATUS_STYLE = {
    "queued":     (WARNING,  WARNING_B,  "QUEUED"),
    "processing": (ACCENT_L, ACCENT_BG,  "PROCESSING"),
    "completed":  (SUCCESS,  SUCCESS_B,  "DONE"),
    "failed":     (ERROR,    ERROR_B,    "FAILED"),
    "cancelled":  (TEXT3,    NEUTRAL_B,  "CANCELLED"),
}

class JobCard(tk.Frame):
    def __init__(self, parent, job: TTSJob,
                 on_retry: Callable, on_cancel: Callable, **kw):
        super().__init__(parent, bg=CARD, padx=14, pady=11,
                         highlightthickness=1, highlightbackground=BORDER, **kw)
        self.job        = job
        self._on_retry  = on_retry
        self._on_cancel = on_cancel
        self._out_path  = ""
        self.columnconfigure(1, weight=1)
        self._build()
        self._refresh_badge()

    def _build(self):
        col, bg, lbl = _STATUS_STYLE.get(self.job.status, (TEXT2, NEUTRAL_B, "?"))

        # ── Left: status badge ────────────────────────────────────────
        self._badge = tk.Label(self, text=lbl, bg=bg, fg=col,
                               font=("Segoe UI", 8, "bold"),
                               padx=7, pady=4, width=12, anchor="center")
        self._badge.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(0, 12))

        # ── Centre: text + meta ───────────────────────────────────────
        self._lbl_prev = tk.Label(self, text=self.job.preview, bg=CARD,
                                  fg=TEXT, font=("Segoe UI", 10), anchor="w")
        self._lbl_prev.grid(row=0, column=1, sticky="ew")

        # Meta row
        meta = tk.Frame(self, bg=CARD)
        meta.grid(row=1, column=1, sticky="ew", pady=(2, 0))

        voice_short = self.job.voice.split("·")[0].split("(")[0].strip()
        tk.Label(meta, text=f"🎙 {voice_short}", bg=CARD, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Label(meta, text=f"  {self.job.speed}×", bg=CARD, fg=TEXT3,
                 font=("Segoe UI", 9)).pack(side="left")
        src = self.job.source_name or "text"
        tk.Label(meta, text=f"  · {src}", bg=CARD, fg=TEXT3,
                 font=("Segoe UI", 9)).pack(side="left")

        self._lbl_prog = tk.Label(meta, text="", bg=CARD, fg=ACCENT_L,
                                  font=("Segoe UI", 9))
        self._lbl_prog.pack(side="left", padx=(12, 0))

        # Output / error (row 2 — hidden until needed)
        self._lbl_out = tk.Label(self, text="", bg=CARD, fg=SUCCESS,
                                 font=("Segoe UI", 9), anchor="w")
        self._lbl_err = tk.Label(self, text="", bg=CARD, fg=ERROR,
                                 font=("Segoe UI", 9), anchor="w", wraplength=520)

        # ── Right: controls ───────────────────────────────────────────
        right = tk.Frame(self, bg=CARD)
        right.grid(row=0, column=2, rowspan=3, sticky="ns", padx=(8, 0))

        # Timestamp
        ts = self.job.created_at.strftime("%H:%M:%S")
        tk.Label(right, text=ts, bg=CARD, fg=TEXT3,
                 font=("Segoe UI", 8)).pack(anchor="ne")

        # Duration (populated on completion)
        self._lbl_dur = tk.Label(right, text="", bg=CARD, fg=TEXT2,
                                  font=("Segoe UI", 8))
        self._lbl_dur.pack(anchor="e")

        # Action buttons (shown as needed)
        self._btn_play   = _btn(right, "▶  Play",   self._play_audio,
                                 bg=ACCENT_BG, fg=ACCENT_L, hover=CARD_HVR,
                                 font=("Segoe UI", 8), padx=8, pady=3)
        self._btn_open   = _btn(right, "📂  Folder", self._open_folder,
                                 bg=CARD_HVR, fg=TEXT2, hover=BORDER,
                                 font=("Segoe UI", 8), padx=8, pady=3)
        self._btn_retry  = _btn(right, "⟳  Retry",  self._do_retry,
                                 bg=WARNING_B, fg=WARNING, hover=CARD_HVR,
                                 font=("Segoe UI", 8), padx=8, pady=3)
        self._btn_cancel = _btn(right, "✕  Cancel", self._do_cancel,
                                 bg=CARD_HVR, fg=TEXT3, hover=BORDER,
                                 font=("Segoe UI", 8), padx=8, pady=3)
        if self.job.status == "queued":
            self._btn_cancel.pack(anchor="e", pady=(2, 0))

    # ── State transitions ─────────────────────────────────────────────────────

    def mark_started(self):
        self.job.status = "processing"
        self._lbl_prog.configure(text="Starting…")
        self._btn_cancel.pack_forget()
        self._refresh_badge()

    def set_progress(self, msg: str):
        self._lbl_prog.configure(text=msg)

    def mark_completed(self, path: str):
        self._out_path  = path
        self.job.status = "completed"
        self._lbl_prog.configure(text="")
        self._lbl_out.configure(text=f"✓  {Path(path).name}")
        self._lbl_out.grid(row=2, column=1, sticky="ew", pady=(3, 0))
        self._lbl_dur.configure(text=self.job.duration_str)
        self._btn_play.pack(anchor="e", pady=(2, 0))
        self._btn_open.pack(anchor="e", pady=(2, 0))
        self._refresh_badge()

    def mark_failed(self, err: str):
        self.job.status = "failed"
        self._lbl_prog.configure(text="")
        short = err[:110] + "…" if len(err) > 110 else err
        self._lbl_err.configure(text=f"✗  {short}")
        self._lbl_err.grid(row=2, column=1, sticky="ew", pady=(3, 0))
        self._lbl_dur.configure(text=self.job.duration_str)
        self._btn_retry.pack(anchor="e", pady=(2, 0))
        self._refresh_badge()

    def mark_cancelled(self):
        self.job.status = "cancelled"
        self._lbl_prog.configure(text="Cancelled")
        self._btn_cancel.pack_forget()
        self._refresh_badge()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _refresh_badge(self):
        col, bg, lbl = _STATUS_STYLE.get(self.job.status, (TEXT2, NEUTRAL_B, "?"))
        self._badge.configure(text=lbl, fg=col, bg=bg)

    def _play_audio(self):
        if self._out_path and Path(self._out_path).exists():
            _open_path(self._out_path)

    def _open_folder(self):
        if self._out_path:
            folder = str(Path(self._out_path).parent)
            _open_path(folder)

    def _do_retry(self):
        self._on_retry(self.job.job_id)

    def _do_cancel(self):
        self._on_cancel(self.job.job_id)
        self.mark_cancelled()


# ═══════════════════════════════════════════════════════════════════════════════
#  Voice Card  (Voices page)
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceCard(tk.Frame):
    def __init__(self, parent, name: str, info: dict,
                 selected: bool, on_select: Callable, **kw):
        g    = info.get("gender", "neutral")
        cbg  = FEMALE_BG  if g == "female"  else (MALE_BG  if g == "male"  else NEUTRAL_BG)
        acc  = FEMALE_ACC if g == "female"  else (MALE_ACC if g == "male"  else NEUTRAL_ACC)
        brd  = acc if selected else BORDER
        super().__init__(parent, bg=cbg, padx=14, pady=13,
                         highlightthickness=2 if selected else 1,
                         highlightbackground=brd, **kw)
        self.bind("<Enter>", lambda e: self.configure(highlightbackground=acc))
        self.bind("<Leave>", lambda e: self.configure(highlightbackground=brd))

        sym = "♀" if g == "female" else ("♂" if g == "male" else "◎")

        hdr = tk.Frame(self, bg=cbg); hdr.pack(fill="x")
        tk.Label(hdr, text=sym, bg=cbg, fg=acc,
                 font=("Segoe UI", 16)).pack(side="left")
        tk.Label(hdr, text=name, bg=cbg, fg=TEXT,
                 font=("Segoe UI", 10, "bold"),
                 wraplength=155, justify="left").pack(side="left", padx=(8, 0))

        lang_nice = "American English" if info.get("lang","") == "en-us" else \
                    "British English"  if info.get("lang","") == "en-gb" else \
                    info.get("lang","")
        tk.Label(self, text=f"ID: {info.get('id', info.get('speaker',''))}",
                 bg=cbg, fg=acc, font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", pady=(8, 0))
        tk.Label(self, text=f"{lang_nice}  ·  Kokoro-82M  ·  24 kHz",
                 bg=cbg, fg=TEXT2, font=("Segoe UI", 9),
                 anchor="w").pack(fill="x")
        tk.Label(self, text=info.get("desc", ""),
                 bg=cbg, fg=TEXT2, font=("Segoe UI", 9),
                 anchor="w", wraplength=170, justify="left").pack(fill="x", pady=(3, 10))

        if selected:
            tk.Label(self, text="✓  Active", bg=cbg, fg=acc,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
        else:
            _btn(self, "Select Voice", lambda n=name: on_select(n),
                 bg=acc, fg="#050d05", hover=acc,
                 font=("Segoe UI", 9, "bold"), padx=10, pady=5)


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: Synthesize
# ═══════════════════════════════════════════════════════════════════════════════

class SynthesizePage(tk.Frame):
    PLACEHOLDER = ("Type or paste text here…\n\n"
                   "Any length is supported — long texts are automatically\n"
                   "chunked and merged into one seamless WAV file.\n\n"
                   "Tip: use  Ctrl+Enter  to add to queue quickly.")

    def __init__(self, parent, cfg: dict, qm: QueueManager,
                 on_status: Callable, on_navigate: Callable, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cfg        = cfg
        self._qm         = qm
        self._status     = on_status
        self._navigate   = on_navigate   # fn(page_name) to switch pages
        self._ph         = True
        self._src        = "text_input"
        self._file_list: list[tuple] = []   # (path, stem, text)
        self._tab        = "text"           # "text" | "files"
        self._build()

    def _build(self):
        # ── Page header ────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 10))
        tk.Label(hdr, text="Synthesize", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        # Keyboard hint
        tk.Label(hdr, text="Ctrl+Enter = queue • Ctrl+L = load file",
                 bg=BG, fg=TEXT3, font=("Segoe UI", 9)).pack(
                     side="right", pady=(8, 0))
        _sep(self).pack(fill="x", padx=24)

        # ── Body: left editor | right controls ─────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=12)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(2, weight=2, minsize=290)
        body.rowconfigure(0, weight=1)

        # ── LEFT ───────────────────────────────────────────────────────
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        # Tab switcher
        tab_bar = tk.Frame(left, bg=BG)
        tab_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._tab_btns: dict[str, tk.Button] = {}
        for key, lbl in [("text", "📝  Text Input"), ("files", "📁  Multi-File")]:
            b = tk.Button(tab_bar, text=lbl,
                          bg=ACCENT if key == "text" else CARD,
                          fg="white" if key == "text" else TEXT2,
                          relief="flat", font=("Segoe UI", 9),
                          padx=12, pady=5, cursor="hand2",
                          command=lambda k=key: self._switch_tab(k))
            b.pack(side="left", padx=(0, 4))
            self._tab_btns[key] = b

        # Stacked content area
        self._text_panel = tk.Frame(left, bg=BG)
        self._text_panel.rowconfigure(0, weight=1)
        self._text_panel.columnconfigure(0, weight=1)
        self._text_panel.grid(row=1, column=0, sticky="nsew")

        self._files_panel = tk.Frame(left, bg=BG)
        self._files_panel.rowconfigure(1, weight=1)
        self._files_panel.columnconfigure(0, weight=1)
        # (hidden initially)

        self._build_text_panel()
        self._build_files_panel()

        # Bottom bar (word count + file label)
        bot = tk.Frame(left, bg=BG)
        bot.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self._count_v = tk.StringVar(value="0 words · 0 chars")
        tk.Label(bot, textvariable=self._count_v, bg=BG, fg=TEXT3,
                 font=("Segoe UI", 9)).pack(side="left")
        self._src_lbl_v = tk.StringVar(value="")
        tk.Label(bot, textvariable=self._src_lbl_v, bg=BG, fg=ACCENT_L,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))

        # ── DIVIDER ────────────────────────────────────────────────────
        tk.Frame(body, bg=BORDER, width=1).grid(row=0, column=1,
                                                  sticky="ns", padx=8)

        # ── RIGHT controls ─────────────────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)

        row_n = 0

        def sect(t, r):
            nonlocal row_n
            tk.Label(right, text=t, bg=BG, fg=TEXT2,
                     font=("Segoe UI", 8, "bold")).grid(
                         row=r, column=0, sticky="w", pady=(10, 3))

        # Voice
        sect("🎙  VOICE", 0)
        voices = list(VOICE_CATALOGUE.keys())
        self._voice_v = tk.StringVar(value=self._cfg.get("voice", voices[0]))
        if self._voice_v.get() not in voices:
            self._voice_v.set(voices[0])
        cb = ttk.Combobox(right, textvariable=self._voice_v,
                           values=voices, state="readonly", font=("Segoe UI", 9))
        cb.grid(row=1, column=0, sticky="ew")
        cb.bind("<<ComboboxSelected>>", self._on_voice_changed)

        self._vinfo_v = tk.StringVar()
        self._vinfo_lbl = tk.Label(right, textvariable=self._vinfo_v,
                                    bg=BG, fg=TEXT2, font=("Segoe UI", 9))
        self._vinfo_lbl.grid(row=2, column=0, sticky="w", pady=(2, 0))
        self._refresh_vinfo()

        # Speed
        sect("🎚  SPEED", 3)
        spd_row = tk.Frame(right, bg=BG)
        spd_row.grid(row=4, column=0, sticky="ew")
        spd_row.columnconfigure(0, weight=1)
        self._speed_v = tk.DoubleVar(value=float(self._cfg.get("speed", 1.0)))
        ttk.Scale(spd_row, from_=0.5, to=2.0, orient="horizontal",
                  variable=self._speed_v,
                  command=lambda v: self._speed_lbl_v.set(
                      f"{float(v):.1f}×")).grid(row=0, column=0, sticky="ew")
        self._speed_lbl_v = tk.StringVar(value=f"{self._speed_v.get():.1f}×")
        tk.Label(spd_row, textvariable=self._speed_lbl_v,
                 bg=BG, fg=ACCENT_L, font=("Segoe UI", 11, "bold"),
                 width=5).grid(row=0, column=1, padx=(6, 0))

        ticks = tk.Frame(right, bg=BG)
        ticks.grid(row=5, column=0, sticky="ew")
        ticks.columnconfigure(0, weight=1); ticks.columnconfigure(1, weight=1)
        tk.Label(ticks, text="0.5×", bg=BG, fg=TEXT3,
                 font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
        tk.Label(ticks, text="2.0×", bg=BG, fg=TEXT3,
                 font=("Segoe UI", 8)).grid(row=0, column=1, sticky="e")

        # Output folder
        sect("📁  OUTPUT FOLDER", 6)
        of_row = tk.Frame(right, bg=BG)
        of_row.grid(row=7, column=0, sticky="ew")
        of_row.columnconfigure(0, weight=1)
        self._outdir_v = tk.StringVar(value=self._cfg.get("output_dir", ""))
        tk.Label(of_row, textvariable=self._outdir_v,
                 bg=CARD, fg=TEXT2, font=("Segoe UI", 9),
                 relief="flat", padx=8, pady=5,
                 anchor="w").grid(row=0, column=0, sticky="ew")
        _btn(of_row, "…", self._pick_outdir,
             bg=BORDER2, fg=TEXT, hover=BORDER,
             font=("Segoe UI", 9), padx=8, pady=4).grid(row=0, column=1, padx=(4, 0))

        _sep(right).grid(row=8, column=0, sticky="ew", pady=10)

        # Action buttons
        self._btn_add = _btn(right, "➕  Add to Queue", self._add_single,
                              bg=ACCENT, fg="white", hover=ACCENT_L,
                              font=("Segoe UI", 11, "bold"), padx=16, pady=12)
        self._btn_add.grid(row=9, column=0, sticky="ew")
        Tooltip(self._btn_add, "Add current text/files to queue  [Ctrl+Enter]")

        self._btn_queue_all = _btn(right, "📋  Queue All Files",
                                    self._add_all_files,
                                    bg=ACCENT_BG, fg=ACCENT_L,
                                    hover=CARD_HVR, font=("Segoe UI", 10, "bold"),
                                    padx=16, pady=8)
        # shown only in Files tab

        _btn(right, "🗑  Clear", self._clear_all,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=5).grid(
                 row=11, column=0, sticky="ew", pady=(6, 0))

        # Keyboard bindings
        self.bind_all("<Control-Return>", lambda e: self._add_single())
        self.bind_all("<Control-l>",      lambda e: self._load_files_dialog())
        self.bind_all("<Control-L>",      lambda e: self._load_files_dialog())

    # ── Text panel ─────────────────────────────────────────────────────────────

    def _build_text_panel(self):
        p = self._text_panel
        tf = tk.Frame(p, bg=CARD, highlightthickness=1, highlightbackground=BORDER2)
        tf.grid(row=0, column=0, sticky="nsew")
        tf.rowconfigure(0, weight=1); tf.columnconfigure(0, weight=1)
        self._txt = tk.Text(
            tf, bg=CARD, fg=TEXT2, font=("Segoe UI", 11),
            relief="flat", bd=0, wrap="word", undo=True,
            insertbackground=TEXT, selectbackground=ACCENT,
            selectforeground=TEXT, padx=12, pady=10)
        tsb = ttk.Scrollbar(tf, command=self._txt.yview)
        self._txt.configure(yscrollcommand=tsb.set)
        self._txt.grid(row=0, column=0, sticky="nsew")
        tsb.grid(row=0, column=1, sticky="ns")
        self._txt.insert("1.0", self.PLACEHOLDER)
        self._txt.bind("<FocusIn>",   self._ph_in)
        self._txt.bind("<FocusOut>",  self._ph_out)
        self._txt.bind("<KeyRelease>", self._update_count)

        # File load button at bottom of text panel
        tbf = tk.Frame(p, bg=BG); tbf.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        _btn(tbf, "📂  Load File(s)…", self._load_files_dialog,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=5).pack(side="right")

    # ── Files panel ────────────────────────────────────────────────────────────

    def _build_files_panel(self):
        p = self._files_panel

        ctrl = tk.Frame(p, bg=BG); ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        _btn(ctrl, "📂  Add Files…", self._load_files_dialog,
             bg=ACCENT, fg="white", hover=ACCENT_L,
             font=("Segoe UI", 9, "bold"), padx=10, pady=5).pack(side="left")
        _btn(ctrl, "📁  Add Project Folders…", self._load_project_folders_dialog,
             bg=ACCENT_BG, fg=ACCENT_L, hover=CARD_HVR,
             font=("Segoe UI", 9, "bold"), padx=10, pady=5).pack(side="left", padx=(6, 0))
        _btn(ctrl, "✕  Clear All", self._clear_file_list,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=5).pack(side="left", padx=(6, 0))
        self._file_count_v = tk.StringVar(value="No files loaded")
        tk.Label(ctrl, textvariable=self._file_count_v, bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="right")

        # File list frame (scrollable)
        list_outer = tk.Frame(p, bg=CARD, highlightthickness=1,
                               highlightbackground=BORDER2)
        list_outer.grid(row=1, column=0, sticky="nsew")
        list_outer.rowconfigure(0, weight=1); list_outer.columnconfigure(0, weight=1)

        self._file_scroll = ScrollFrame(list_outer, bg=CARD)
        self._file_scroll.pack(fill="both", expand=True)

        # Empty state
        self._file_empty = tk.Label(
            self._file_scroll.inner,
            text="No files loaded.\nClick  📂 Add Files…  to load .txt files.",
            bg=CARD, fg=TEXT3, font=("Segoe UI", 10), justify="center")
        self._file_empty.pack(pady=60)

    def _rebuild_file_list(self):
        for w in self._file_scroll.inner.winfo_children():
            if w is not self._file_empty:
                w.destroy()

        if not self._file_list:
            self._file_empty.pack(pady=60)
            self._file_count_v.set("No files loaded")
            self._count_v.set("0 words · 0 chars")
            return

        self._file_empty.pack_forget()
        total_w = total_c = 0
        for i, (path, stem, text) in enumerate(self._file_list):
            row = tk.Frame(self._file_scroll.inner, bg=CARD,
                           highlightthickness=1, highlightbackground=BORDER)
            row.pack(fill="x", padx=4, pady=2)
            row.columnconfigure(1, weight=1)

            # Index
            tk.Label(row, text=f"{i+1:02d}", bg=CARD, fg=TEXT3,
                     font=("Consolas", 9), padx=8, pady=6).grid(row=0, column=0)

            # Name + stats
            info = tk.Frame(row, bg=CARD)
            info.grid(row=0, column=1, sticky="ew")
            tk.Label(info, text=Path(path).name, bg=CARD, fg=TEXT,
                     font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            wc = len(text.split()); cc = len(text)
            tk.Label(info, text=f"{wc:,} words · {cc:,} chars",
                     bg=CARD, fg=TEXT2, font=("Segoe UI", 9), anchor="w").pack(fill="x")
            total_w += wc; total_c += cc

            # Remove button
            _btn(row, "✕", lambda i=i: self._remove_file(i),
                 bg=CARD, fg=TEXT3, hover=CARD_HVR,
                 font=("Segoe UI", 9), padx=6, pady=4).grid(row=0, column=2, padx=(4, 6))

        n = len(self._file_list)
        self._file_count_v.set(f"{n} file{'s' if n>1 else ''}  ·  "
                                f"{total_w:,} words total")
        self._count_v.set(f"{total_w:,} words · {total_c:,} chars  (all files)")

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _switch_tab(self, tab: str):
        self._tab = tab
        for k, b in self._tab_btns.items():
            b.configure(bg=ACCENT if k == tab else CARD,
                        fg="white" if k == tab else TEXT2)
        if tab == "text":
            self._files_panel.grid_forget()
            self._text_panel.grid(row=1, column=0, sticky="nsew")
            self._btn_queue_all.grid_forget()
        else:
            self._text_panel.grid_forget()
            self._files_panel.grid(row=1, column=0, sticky="nsew")
            self._btn_queue_all.grid(row=10, column=0, sticky="ew", pady=(6, 0))

    # ── Placeholder helpers ────────────────────────────────────────────────────

    def _ph_in(self, _):
        if self._ph:
            self._txt.delete("1.0", "end")
            self._txt.configure(fg=TEXT)
            self._ph = False

    def _ph_out(self, _):
        if not self._txt.get("1.0", "end").strip():
            self._txt.insert("1.0", self.PLACEHOLDER)
            self._txt.configure(fg=TEXT2)
            self._ph = True

    def _get_text(self) -> str:
        return "" if self._ph else self._txt.get("1.0", "end").strip()

    def _update_count(self, _=None):
        t = self._get_text()
        self._count_v.set(f"{len(t.split()):,} words · {len(t):,} chars" if t
                          else "0 words · 0 chars")

    # ── File operations ────────────────────────────────────────────────────────

    def _load_files_dialog(self):
        paths = filedialog.askopenfilenames(
            title="Load Text File(s)",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if not paths:
            return
        results = load_multiple_files(list(paths))
        if len(results) == 1:
            # Single file: load into text editor
            path, stem, text = results[0]
            self._switch_tab("text")
            self._ph = False
            self._txt.configure(fg=TEXT)
            self._txt.delete("1.0", "end")
            self._txt.insert("1.0", text)
            self._src = stem
            self._src_lbl_v.set(f"📄 {Path(path).name}")
            self._update_count()
            self._status(f"Loaded: {Path(path).name}  ({len(text):,} chars)")
        else:
            # Multiple files: go to Files tab
            self._file_list.extend(results)
            self._rebuild_file_list()
            self._switch_tab("files")
            self._status(f"Loaded {len(results)} files into queue list")

    def _load_project_folders_dialog(self):
        """Open the universal multi-folder selector and queue every valid project folder."""
        initial = Path(self._cfg.get("output_dir", str(Path.home())))
        folders = ask_folders(
            parent=self.winfo_toplevel(),
            title="Select Project Folders",
            initial_dir=initial,
        )
        if not folders:
            return

        import json

        count   = 0
        skipped = 0
        for folder in folders:
            script_path = folder / "script.txt"
            if not script_path.exists():
                log.warn(f"Skipped {folder.name} — no script.txt found")
                self._status(f"Skipped: {folder.name} (missing script.txt)")
                skipped += 1
                continue

            text = read_text_file(str(script_path))
            if not text:
                skipped += 1
                continue

            # ── Voice selection from metadata.json ────────────────────────
            voice = self._voice_v.get()
            speed = round(float(self._speed_v.get()), 1)

            meta_path = folder / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(read_text_file(str(meta_path)))
                    preset_name = meta.get("preset_name", "")

                    # Match preset name against voice catalogue
                    if preset_name:
                        voices = list(VOICE_CATALOGUE.keys())
                        for v in voices:
                            if preset_name.lower() in v.lower():
                                voice = v
                                break
                except Exception:
                    pass

            # ── Output goes into the project folder per contract ──────────
            out  = str(folder / "audio.wav")
            stem = folder.name

            job = TTSJob(text=text, voice=voice, output_path=out,
                         speed=speed,
                         chunk_limit=self._cfg.get("chunk_limit", CFG.CHUNK_CHAR_LIMIT),
                         source_name=stem)
            self._qm.enqueue(job)
            count += 1
            log.info(f"Project folder queued: {folder.name}  voice='{voice}'")

        if count > 0:
            msg = f"✓  {count} project folder(s) added to queue"
            if skipped:
                msg += f"  ({skipped} skipped)"
            self._status(msg)
            self._navigate("queue")
        else:
            self._status("No valid project folders found.")

    def _remove_file(self, idx: int):
        if 0 <= idx < len(self._file_list):
            self._file_list.pop(idx)
            self._rebuild_file_list()

    def _clear_file_list(self):
        self._file_list.clear()
        self._rebuild_file_list()

    # ── Queue actions ──────────────────────────────────────────────────────────

    def _add_single(self):
        if self._tab == "files":
            self._add_all_files()
            return
        text = self._get_text()
        if not text:
            self._status("⚠  Please enter some text first.")
            return
        self._queue_text(text, self._src)
        self._clear_text_only()
        self._navigate("queue")

    def _add_all_files(self):
        if not self._file_list:
            self._status("⚠  No files loaded. Use  📂 Add Files…  first.")
            return
        voice  = self._voice_v.get()
        speed  = round(float(self._speed_v.get()), 1)
        outdir = self._cfg.get("output_dir", str(Path.home() / "tts_output"))
        self._cfg.update({"voice": voice, "speed": speed})
        CFG.save(self._cfg)
        count = 0
        for path, stem, text in self._file_list:
            if not text or text.startswith("[ERROR"):
                continue
            out = build_output_path(
                outdir, stem,
                self._cfg.get("output_template", "{name}_{ts}"),
                voice, speed)
            job = TTSJob(text=text, voice=voice, output_path=out,
                         speed=speed, chunk_limit=self._cfg.get("chunk_limit", CFG.CHUNK_CHAR_LIMIT),
                         source_name=stem)
            self._qm.enqueue(job)
            count += 1
        self._file_list.clear()
        self._rebuild_file_list()
        self._status(f"✓  {count} file job{'s' if count > 1 else ''} added to queue")
        self._navigate("queue")

    def _queue_text(self, text: str, source: str):
        voice  = self._voice_v.get()
        speed  = round(float(self._speed_v.get()), 1)
        outdir = self._cfg.get("output_dir", str(Path.home() / "tts_output"))
        self._cfg.update({"voice": voice, "speed": speed})
        CFG.save(self._cfg)
        out = build_output_path(
            outdir, source,
            self._cfg.get("output_template", "{name}_{ts}"),
            voice, speed)
        job = TTSJob(text=text, voice=voice, output_path=out,
                     speed=speed, chunk_limit=self._cfg.get("chunk_limit", CFG.CHUNK_CHAR_LIMIT),
                     source_name=source)
        self._qm.enqueue(job)
        self._status(f"✓  Job {job.job_id} added to queue")

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _clear_text_only(self):
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", self.PLACEHOLDER)
        self._txt.configure(fg=TEXT2)
        self._ph = True
        self._src = "text_input"
        self._src_lbl_v.set("")
        self._count_v.set("0 words · 0 chars")

    def _clear_all(self):
        self._clear_text_only()
        self._file_list.clear()
        self._rebuild_file_list()

    def _pick_outdir(self):
        d = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self._cfg.get("output_dir", str(Path.home())))
        if d:
            self._cfg["output_dir"] = d
            self._outdir_v.set(d)
            CFG.save(self._cfg)
            self._status(f"Output folder: {d}")

    def _refresh_vinfo(self):
        v    = self._voice_v.get()
        info = VOICE_CATALOGUE.get(v, {})
        g    = info.get("gender", "").capitalize()
        vid  = info.get("id", "")
        lang_map = {"en-us": "American English", "en-gb": "British English"}
        lang = lang_map.get(info.get("lang", ""), info.get("lang", ""))
        self._vinfo_v.set(f"{vid}  ·  {g}  ·  {lang}  ·  24 kHz")

    def _on_voice_changed(self, _):
        self._refresh_vinfo()
        self._cfg["voice"] = self._voice_v.get()
        CFG.save(self._cfg)

    def set_voice(self, name: str):
        """Called from Voices page."""
        if name in VOICE_CATALOGUE:
            self._voice_v.set(name)
            self._refresh_vinfo()

    def sync_speed(self, speed: float):
        self._speed_v.set(speed)
        self._speed_lbl_v.set(f"{speed:.1f}×")


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: Queue
# ═══════════════════════════════════════════════════════════════════════════════

class QueuePage(tk.Frame):
    def __init__(self, parent, qm: QueueManager, on_status: Callable, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._qm     = qm
        self._status = on_status
        self._cards: dict[str, JobCard] = {}
        self._filter = "all"
        self._build()

    def _build(self):
        # ── Header ─────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 10))
        tk.Label(hdr, text="Queue", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")

        btns = tk.Frame(hdr, bg=BG)
        btns.pack(side="right")

        self._btn_pause = _btn(btns, "⏸  Pause", self._toggle_pause,
                                bg=WARNING_B, fg=WARNING, hover=CARD_HVR,
                                font=("Segoe UI", 10, "bold"), padx=14, pady=6)
        self._btn_pause.pack(side="left", padx=(0, 6))
        Tooltip(self._btn_pause,
                "Pause: lets current job finish, then stops.\nResume: continue processing.")

        _btn(btns, "Clear Finished", self._clear_finished,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=12, pady=6).pack(side="left")

        _sep(self).pack(fill="x", padx=24)

        # ── Stats bar ──────────────────────────────────────────────────
        stats = tk.Frame(self, bg=BG)
        stats.pack(fill="x", padx=24, pady=(10, 0))

        self._stat_vars: dict[str, tk.StringVar] = {}
        for key, label, fg, bg in [
            ("total",      "Total",      TEXT,     CARD),
            ("queued",     "Queued",     WARNING,  WARNING_B),
            ("processing", "Active",     ACCENT_L, ACCENT_BG),
            ("completed",  "Completed",  SUCCESS,  SUCCESS_B),
            ("failed",     "Failed",     ERROR,    ERROR_B),
        ]:
            f = tk.Frame(stats, bg=bg, padx=14, pady=8,
                         highlightthickness=1, highlightbackground=BORDER)
            f.pack(side="left", padx=(0, 6))
            v = tk.StringVar(value="0")
            self._stat_vars[key] = v
            tk.Label(f, textvariable=v, bg=bg, fg=fg,
                     font=("Segoe UI", 20, "bold")).pack()
            tk.Label(f, text=label, bg=bg, fg=fg,
                     font=("Segoe UI", 8)).pack()

        # Paused indicator (hidden by default)
        self._paused_frame = tk.Frame(stats, bg=PAUSED_B, padx=14, pady=8,
                                       highlightthickness=1,
                                       highlightbackground=BORDER)
        self._paused_lbl = tk.Label(self._paused_frame, text="⏸", bg=PAUSED_B,
                                     fg=PAUSED_C, font=("Segoe UI", 20, "bold"))
        self._paused_lbl.pack()
        tk.Label(self._paused_frame, text="Paused", bg=PAUSED_B, fg=PAUSED_C,
                 font=("Segoe UI", 8)).pack()

        # Progress bar
        prog_f = tk.Frame(self, bg=BG)
        prog_f.pack(fill="x", padx=24, pady=(8, 0))
        prog_f.columnconfigure(0, weight=1)
        self._prog_bar = ttk.Progressbar(prog_f, mode="determinate", length=400)
        self._prog_bar.grid(row=0, column=0, sticky="ew")
        self._prog_lbl_v = tk.StringVar(value="")
        tk.Label(prog_f, textvariable=self._prog_lbl_v,
                 bg=BG, fg=TEXT3, font=("Segoe UI", 9),
                 width=18, anchor="e").grid(row=0, column=1, padx=(6, 0))

        # ── Filter row ─────────────────────────────────────────────────
        filt = tk.Frame(self, bg=BG)
        filt.pack(fill="x", padx=24, pady=(8, 0))
        tk.Label(filt, text="Filter:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._filt_btns: dict[str, tk.Button] = {}
        for key, lbl in [("all", "All"), ("queued", "Queued"),
                          ("processing", "Active"), ("completed", "Completed"),
                          ("failed", "Failed")]:
            is_a = key == "all"
            b = tk.Button(filt, text=lbl,
                          bg=ACCENT if is_a else CARD,
                          fg="white" if is_a else TEXT2,
                          relief="flat", font=("Segoe UI", 9),
                          padx=10, pady=4, cursor="hand2",
                          command=lambda k=key: self._set_filter(k))
            b.pack(side="left", padx=(0, 3))
            self._filt_btns[key] = b

        # ── Empty state ────────────────────────────────────────────────
        self._empty = tk.Frame(self, bg=BG)
        self._empty.pack(fill="both", expand=True)
        tk.Label(self._empty, text="📋", bg=BG, fg=TEXT3,
                 font=("Segoe UI", 42)).pack(pady=(50, 8))
        tk.Label(self._empty, text="Queue is empty",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 13, "bold")).pack()
        tk.Label(self._empty,
                 text="Go to Synthesize, enter text or load files, then click Add to Queue.",
                 bg=BG, fg=TEXT3, font=("Segoe UI", 10)).pack(pady=4)

        # ── Scrollable job list ────────────────────────────────────────
        self._scroll = ScrollFrame(self, bg=BG)

    # ── Pause / Resume ────────────────────────────────────────────────────────

    def _toggle_pause(self):
        if self._qm.is_paused():
            self._qm.resume()
        elif self._qm.is_pausing():
            pass   # wait for it
        else:
            self._qm.pause()

    def update_pause_btn(self, state: str):
        """state: running | pausing | paused"""
        if state == "running":
            self._btn_pause.configure(text="⏸  Pause",
                                       bg=WARNING_B, fg=WARNING)
            self._paused_frame.pack_forget()
        elif state == "pausing":
            self._btn_pause.configure(text="⏸  Pausing…",
                                       bg=CARD, fg=TEXT3)
            self._paused_frame.pack_forget()
        else:  # paused
            self._btn_pause.configure(text="▶  Resume",
                                       bg=SUCCESS_B, fg=SUCCESS)
            self._paused_frame.pack(side="left", padx=(0, 6))

    # ── Queue events ──────────────────────────────────────────────────────────

    def on_queued(self, job: TTSJob):
        if not self._cards:
            self._empty.pack_forget()
            self._scroll.pack(fill="both", expand=True, padx=24, pady=(8, 12))
        card = JobCard(self._scroll.inner, job,
                       on_retry=self._retry_job,
                       on_cancel=self._cancel_job)
        card.pack(fill="x", pady=(0, 5))
        self._cards[job.job_id] = card
        self._scroll.scroll_bottom()
        self._refresh_stats()

    def on_started(self, jid: str):
        if c := self._cards.get(jid):
            c.mark_started()
            self._scroll.scroll_to(c)
        self._refresh_stats()

    def on_progress(self, jid: str, msg: str):
        if c := self._cards.get(jid):
            c.set_progress(msg)

    def on_completed(self, jid: str, path: str):
        if c := self._cards.get(jid): c.mark_completed(path)
        self._refresh_stats()

    def on_failed(self, jid: str, err: str):
        if c := self._cards.get(jid): c.mark_failed(err)
        self._refresh_stats()

    def on_cancelled(self, jid: str):
        if c := self._cards.get(jid): c.mark_cancelled()
        self._refresh_stats()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _retry_job(self, job_id: str):
        new_job = self._qm.retry(job_id)
        if new_job:
            self._status(f"Retrying job {job_id} as {new_job.job_id}")
        else:
            self._status(f"Cannot retry job {job_id}")

    def _cancel_job(self, job_id: str):
        self._qm.cancel_queued(job_id)
        self._refresh_stats()
        self._status(f"Cancelled job {job_id}")

    def _refresh_stats(self):
        jobs = list(self._cards.values())
        total  = len(jobs)
        q_ct   = sum(1 for j in jobs if j.job.status == "queued")
        p_ct   = sum(1 for j in jobs if j.job.status == "processing")
        done   = sum(1 for j in jobs if j.job.status == "completed")
        failed = sum(1 for j in jobs if j.job.status == "failed")
        self._stat_vars["total"].set(str(total))
        self._stat_vars["queued"].set(str(q_ct))
        self._stat_vars["processing"].set(str(p_ct))
        self._stat_vars["completed"].set(str(done))
        self._stat_vars["failed"].set(str(failed))
        # Progress bar
        if total > 0:
            pct = (done + failed) / total * 100
            self._prog_bar["value"] = pct
            self._prog_lbl_v.set(f"{done + failed} / {total}")
        else:
            self._prog_bar["value"] = 0
            self._prog_lbl_v.set("")

    def pending_count(self) -> int:
        return sum(1 for c in self._cards.values()
                   if c.job.status in ("queued", "processing"))

    def _set_filter(self, key: str):
        self._filter = key
        for k, b in self._filt_btns.items():
            b.configure(bg=ACCENT if k == key else CARD,
                        fg="white" if k == key else TEXT2)
        for card in self._cards.values():
            s = card.job.status
            show = (key == "all" or s == key or
                    (key == "processing" and s == "queued"))
            if show: card.pack(fill="x", pady=(0, 5))
            else:    card.pack_forget()

    def _clear_finished(self):
        done = [jid for jid, c in self._cards.items()
                if c.job.status in ("completed", "failed", "cancelled")]
        for jid in done:
            self._cards.pop(jid).destroy()
        if not self._cards:
            self._scroll.pack_forget()
            self._empty.pack(fill="both", expand=True)
        self._refresh_stats()


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: Voices
# ═══════════════════════════════════════════════════════════════════════════════

class VoicesPage(tk.Frame):
    def __init__(self, parent, cfg: dict, on_select: Callable, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cfg       = cfg
        self._on_select = on_select
        self._filter_g  = "all"   # all | female | male | neutral
        self._search    = ""
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(hdr, text="Voices", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(hdr, text=f"  ·  {len(VOICE_CATALOGUE)} voices  ·  Kokoro-82M  ·  Apache 2.0",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(side="left", pady=(6, 0))
        _sep(self).pack(fill="x", padx=24)

        # ── Filters + search bar ───────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=24, pady=(10, 6))

        # Gender filter
        for key, lbl, acc in [
            ("all",     "All",     ACCENT),
            ("female",  "♀ Female",  FEMALE_ACC),
            ("male",    "♂ Male",    MALE_ACC),
            ("neutral", "◎ Neutral", NEUTRAL_ACC),
        ]:
            is_a = key == "all"
            b = tk.Button(ctrl, text=lbl,
                          bg=acc if is_a else CARD,
                          fg="white" if is_a else TEXT2,
                          relief="flat", font=("Segoe UI", 9),
                          padx=10, pady=4, cursor="hand2",
                          command=lambda k=key: self._set_gender_filter(k))
            b.pack(side="left", padx=(0, 4))

        # Search
        tk.Label(ctrl, text="Search:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="right", padx=(0, 6))
        self._search_v = tk.StringVar()
        self._search_v.trace_add("write", lambda *a: self._refresh_grid())
        se = tk.Entry(ctrl, textvariable=self._search_v,
                      bg=CARD, fg=TEXT, insertbackground=TEXT,
                      relief="flat", font=("Segoe UI", 10), width=16,
                      highlightthickness=1, highlightbackground=BORDER2)
        se.pack(side="right")

        self._scroll = ScrollFrame(self, bg=BG)
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._refresh_grid()

    def _set_gender_filter(self, key: str):
        self._filter_g = key
        self._refresh_grid()

    def _refresh_grid(self):
        for w in self._scroll.inner.winfo_children():
            w.destroy()

        search   = self._search_v.get().lower()
        selected = self._cfg.get("voice", "")
        voices   = [
            (n, i) for n, i in VOICE_CATALOGUE.items()
            if (self._filter_g == "all" or i.get("gender") == self._filter_g)
            and (not search or search in n.lower() or
                 search in i.get("desc", "").lower() or
                 search in i.get("speaker", "").lower())
        ]

        if not voices:
            tk.Label(self._scroll.inner,
                     text="No voices match the current filter.",
                     bg=BG, fg=TEXT3, font=("Segoe UI", 11)).pack(pady=60)
            return

        self._scroll.inner.columnconfigure(0, weight=1, uniform="vc")
        self._scroll.inner.columnconfigure(1, weight=1, uniform="vc")

        for i, (name, info) in enumerate(voices):
            r, c = divmod(i, 2)
            card = VoiceCard(self._scroll.inner, name, info,
                              selected=(name == selected),
                              on_select=self._select)
            card.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)

    def _select(self, name: str):
        self._cfg["voice"] = name
        CFG.save(self._cfg)
        self._refresh_grid()
        self._on_select(name)

    def refresh(self):
        self._refresh_grid()


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: History  (persistent completed-job log)
# ═══════════════════════════════════════════════════════════════════════════════

class HistoryPage(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._entries: list[dict] = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 10))
        tk.Label(hdr, text="History", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        _btn(hdr, "Export CSV", self._export_csv,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=5).pack(side="right")
        _btn(hdr, "Clear History", self._clear_history,
             bg=ERROR_B, fg=ERROR, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=5).pack(side="right", padx=(0, 6))
        _sep(self).pack(fill="x", padx=24)

        # Column headers
        ch = tk.Frame(self, bg=SURFACE)
        ch.pack(fill="x", padx=24, pady=(8, 0))
        ch.columnconfigure(1, weight=1)
        for col, (lbl, w) in enumerate([
            ("#", 4), ("Preview", 0), ("Voice", 14),
            ("Speed", 5), ("Duration", 8), ("Time", 10), ("File", 14),
        ]):
            tk.Label(ch, text=lbl, bg=SURFACE, fg=TEXT2,
                     font=("Segoe UI", 9, "bold"),
                     width=w if w else None, anchor="w",
                     padx=6, pady=5).grid(row=0, column=col,
                                           sticky="ew" if col == 1 else "w")
        ch.columnconfigure(1, weight=1)

        self._empty = tk.Frame(self, bg=BG)
        self._empty.pack(fill="both", expand=True)
        tk.Label(self._empty, text="📜", bg=BG, fg=TEXT3,
                 font=("Segoe UI", 36)).pack(pady=(50, 8))
        tk.Label(self._empty, text="No history yet",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 12, "bold")).pack()
        tk.Label(self._empty,
                 text="Completed jobs appear here automatically.",
                 bg=BG, fg=TEXT3, font=("Segoe UI", 10)).pack(pady=4)

        self._scroll = ScrollFrame(self, bg=BG)

    def add_entry(self, job: TTSJob):
        entry = {
            "job_id":    job.job_id,
            "preview":   job.preview,
            "voice":     job.voice,
            "speed":     job.speed,
            "duration":  job.duration_str,
            "time":      job.finished_at.strftime("%H:%M:%S") if job.finished_at else "—",
            "out_path":  job.output_path,
        }
        self._entries.append(entry)

        if len(self._entries) == 1:
            self._empty.pack_forget()
            self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        row = tk.Frame(self._scroll.inner, bg=CARD,
                       highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill="x", pady=(0, 3))
        row.columnconfigure(1, weight=1)

        n = len(self._entries)
        vals = [str(n), entry["preview"][:55],
                entry["voice"].split("·")[0].split("(")[0].strip()[:18],
                f"{entry['speed']}×",
                entry["duration"],
                entry["time"],
                Path(entry["out_path"]).name[:20]]
        widths = [4, 0, 14, 5, 8, 10, 14]

        for col, (val, w) in enumerate(zip(vals, widths)):
            kw_extra = {"width": w} if w else {}
            tk.Label(row, text=val, bg=CARD, fg=TEXT if col == 1 else TEXT2,
                     font=("Segoe UI", 9), anchor="w",
                     padx=6, pady=7, **kw_extra).grid(
                         row=0, column=col, sticky="ew" if col == 1 else "w")
        row.columnconfigure(1, weight=1)

        act_f = tk.Frame(row, bg=CARD)
        act_f.grid(row=0, column=7, sticky="e", padx=(4, 6))
        out = entry["out_path"]
        _btn(act_f, "▶", lambda p=out: _open_path(p),
             bg=ACCENT_BG, fg=ACCENT_L, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=6, pady=3).pack(side="left")
        _btn(act_f, "📂", lambda p=out: _open_path(str(Path(p).parent)),
             bg=CARD_HVR, fg=TEXT2, hover=BORDER,
             font=("Segoe UI", 9), padx=6, pady=3).pack(side="left", padx=(3, 0))

    def _clear_history(self):
        if messagebox.askyesno("Clear History",
                               "Remove all history entries?\n(Output files are not deleted.)"):
            self._entries.clear()
            for w in self._scroll.inner.winfo_children(): w.destroy()
            self._scroll.pack_forget()
            self._empty.pack(fill="both", expand=True)

    def _export_csv(self):
        if not self._entries:
            messagebox.showinfo("Export", "No history to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export History",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt")])
        if not path: return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["job_id","preview","voice","speed",
                               "duration","time","out_path"])
            writer.writeheader()
            writer.writerows(self._entries)
        messagebox.showinfo("Exported", f"History saved to:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: Settings
# ═══════════════════════════════════════════════════════════════════════════════

class SettingsPage(tk.Frame):
    def __init__(self, parent, cfg: dict, on_sync: Callable, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cfg     = cfg
        self._on_sync = on_sync   # notify app of any changes
        self._build()

    def _build(self):
        tk.Label(self, text="Settings", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(
                     anchor="w", padx=24, pady=(18, 10))
        _sep(self).pack(fill="x", padx=24)

        scroll = ScrollFrame(self, bg=BG)
        scroll.pack(fill="both", expand=True)
        p = scroll.inner
        p.columnconfigure(0, weight=1)

        def section(txt):
            tk.Label(p, text=txt, bg=BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold")).pack(
                         anchor="w", padx=24, pady=(22, 5))
            _sep(p).pack(fill="x", padx=24, pady=(0, 8))

        def row_frame():
            f = tk.Frame(p, bg=BG)
            f.pack(fill="x", padx=24, pady=4)
            f.columnconfigure(1, weight=1)
            return f

        # ── Output ─────────────────────────────────────────────────────
        section("📁  OUTPUT")
        f = row_frame()
        tk.Label(f, text="Save folder:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        self._outdir_v = tk.StringVar(value=self._cfg.get("output_dir", ""))
        tk.Label(f, textvariable=self._outdir_v, bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10), padx=10, pady=6,
                 anchor="w").grid(row=0, column=1, sticky="ew", padx=(8, 8))
        _btn(f, "Browse…", self._pick_dir, bg=BORDER2, fg=TEXT, hover=BORDER,
             font=("Segoe UI", 9), padx=12, pady=5).grid(row=0, column=2)

        f2 = row_frame()
        tk.Label(f2, text="Filename template:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        self._tmpl_v = tk.StringVar(value=self._cfg.get("output_template", "{name}_{ts}"))
        te = tk.Entry(f2, textvariable=self._tmpl_v, bg=CARD, fg=TEXT,
                      insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
                      highlightthickness=1, highlightbackground=BORDER2)
        te.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        te.bind("<FocusOut>", self._save_template)
        tk.Label(f2, text="Variables: {name} {ts} {voice} {speed}",
                 bg=BG, fg=TEXT3, font=("Segoe UI", 9)).grid(
                     row=1, column=1, sticky="w", padx=(8, 0))

        # ── Voice & Speed ──────────────────────────────────────────────
        section("🎙  DEFAULT VOICE & SPEED")
        f = row_frame()
        tk.Label(f, text="Default voice:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        voices = list(VOICE_CATALOGUE.keys())
        self._voice_v = tk.StringVar(value=self._cfg.get("voice", voices[0]))
        cb = ttk.Combobox(f, textvariable=self._voice_v, values=voices,
                           state="readonly", font=("Segoe UI", 10))
        cb.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", self._save_voice)

        f = row_frame()
        tk.Label(f, text="Default speed:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        self._speed_v = tk.DoubleVar(value=float(self._cfg.get("speed", 1.0)))
        self._speed_lbl_v = tk.StringVar(value=f"{self._speed_v.get():.1f}×")
        ttk.Scale(f, from_=0.5, to=2.0, orient="horizontal",
                  variable=self._speed_v,
                  command=self._on_speed).grid(
                      row=0, column=1, sticky="ew", padx=(8, 8))
        tk.Label(f, textvariable=self._speed_lbl_v, bg=BG, fg=ACCENT_L,
                 font=("Segoe UI", 11, "bold"), width=5).grid(row=0, column=2)

        # ── Behaviour ─────────────────────────────────────────────────
        section("🔧  BEHAVIOUR")
        self._bool_vars: dict[str, tk.BooleanVar] = {}
        for key, label, tip in [
            ("auto_open_output",   "Open output folder after each job",
             "Automatically reveals the output folder in Explorer/Finder when a job completes."),
            ("auto_clear_done",    "Auto-clear completed jobs from queue view",
             "Completed jobs are removed from the Queue page automatically."),
            ("show_notifications", "Show toast notifications on job completion",
             "Brief popups appear when a job finishes."),
        ]:
            bv = tk.BooleanVar(value=bool(self._cfg.get(key, True)))
            self._bool_vars[key] = bv
            f = row_frame()
            cb_w = tk.Checkbutton(f, text=label, variable=bv,
                                   bg=BG, fg=TEXT, selectcolor=CARD,
                                   activebackground=BG, activeforeground=TEXT,
                                   font=("Segoe UI", 10), cursor="hand2",
                                   command=lambda k=key, v=bv: self._save_bool(k, v))
            cb_w.grid(row=0, column=0, columnspan=2, sticky="w")
            tk.Label(f, text=tip, bg=BG, fg=TEXT3,
                     font=("Segoe UI", 9), wraplength=480).grid(
                         row=1, column=0, columnspan=2, sticky="w", padx=(20, 0))

        # ── Advanced ──────────────────────────────────────────────────
        section("⚙  ADVANCED")
        f = row_frame()
        tk.Label(f, text="Text chunk limit (chars):", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        self._chunk_v = tk.IntVar(value=int(self._cfg.get("chunk_limit", 250)))
        sp = tk.Spinbox(f, from_=80, to=600, increment=10,
                         textvariable=self._chunk_v, width=7,
                         bg=CARD, fg=TEXT, relief="flat",
                         font=("Segoe UI", 10),
                         highlightthickness=1, highlightbackground=BORDER2,
                         buttonbackground=BORDER2, insertbackground=TEXT,
                         command=self._save_chunk)
        sp.grid(row=0, column=1, sticky="w", padx=(8, 0))
        tk.Label(f, text="Safe phoneme chunk limit (Kokoro supports up to ~510 phonemes; 300 chars recommended)",
                 bg=BG, fg=TEXT3, font=("Segoe UI", 9)).grid(
                     row=1, column=1, sticky="w", padx=(8, 0))

        # Model cache info
        f = row_frame()
        try:
            from config.settings import MODEL_DIR
            if MODEL_DIR.exists():
                size_mb = sum(
                    fp.stat().st_size for fp in MODEL_DIR.rglob("*") if fp.is_file()
                ) // (1024 * 1024)
                cache_info = f"{MODEL_DIR}  ({size_mb} MB)"
            else:
                cache_info = f"{MODEL_DIR} (not downloaded yet)"
        except Exception as e:
            cache_info = f"Error reading cache: {e}"
        tk.Label(f, text="Model cache:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10), width=22, anchor="w").grid(row=0, column=0)
        tk.Label(f, text=cache_info, bg=CARD, fg=TEXT3,
                 font=("Segoe UI", 9), padx=10, pady=6,
                 anchor="w").grid(row=0, column=1, sticky="ew", padx=(8, 8))

        # ── About ─────────────────────────────────────────────────────
        section("ℹ  ABOUT")
        about = tk.Frame(p, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        about.pack(fill="x", padx=24, pady=(0, 4))
        for line, fg in [
            (f"LocalTTS v{APP_VERSION}", TEXT),
            ("TTS engine:  Kokoro-82M  (Apache 2.0)  –  thewh1teagle/kokoro-onnx", TEXT2),
            ("Python 3.10 – 3.13  ·  CPU-only  ·  100 % offline after first run", TEXT2),
            ("WAV 24 kHz  ·  18 voices  ·  Unlimited text  ·  Pause / Resume queue", TEXT3),
            ("© 2025 – Apache 2.0 / MIT licence", TEXT3),
        ]:
            tk.Label(about, text=line, bg=CARD, fg=fg,
                     font=("Segoe UI", 10), anchor="w",
                     padx=16, pady=3).pack(fill="x")
        tk.Label(about, text="", bg=CARD).pack(pady=4)

        tk.Label(p, bg=BG).pack(pady=20)

    # ── Save helpers ──────────────────────────────────────────────────────────

    def _pick_dir(self):
        d = filedialog.askdirectory(title="Select Output Folder",
                                     initialdir=self._cfg.get("output_dir", str(Path.home())))
        if d:
            self._cfg["output_dir"] = d
            self._outdir_v.set(d)
            CFG.save(self._cfg)
            self._on_sync()

    def _save_template(self, _=None):
        tmpl = self._tmpl_v.get().strip() or "{name}_{ts}"
        self._cfg["output_template"] = tmpl
        CFG.save(self._cfg)

    def _save_voice(self, _=None):
        self._cfg["voice"] = self._voice_v.get()
        CFG.save(self._cfg)
        self._on_sync()

    def _on_speed(self, val):
        v = float(val)
        self._speed_lbl_v.set(f"{v:.1f}×")
        self._cfg["speed"] = round(v, 1)
        CFG.save(self._cfg)
        self._on_sync()

    def _save_bool(self, key: str, var: tk.BooleanVar):
        self._cfg[key] = var.get()
        CFG.save(self._cfg)

    def _save_chunk(self):
        try:
            self._cfg["chunk_limit"] = int(self._chunk_v.get())
            CFG.save(self._cfg)
        except Exception:
            pass

    def refresh(self):
        voices = list(VOICE_CATALOGUE.keys())
        v = self._cfg.get("voice", voices[0])
        if v in voices: self._voice_v.set(v)
        self._speed_v.set(float(self._cfg.get("speed", 1.0)))
        self._speed_lbl_v.set(f"{self._speed_v.get():.1f}×")
        self._outdir_v.set(self._cfg.get("output_dir", ""))
        for key, bv in self._bool_vars.items():
            bv.set(bool(self._cfg.get(key, True)))
        self._chunk_v.set(int(self._cfg.get("chunk_limit", 250)))


# ═══════════════════════════════════════════════════════════════════════════════
#  App  –  top-level window
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
#  Page: Console  (live log viewer)
# ═══════════════════════════════════════════════════════════════════════════════

_LOG_COLORS = {
    "DEBUG": "#505080",
    "INFO":  "#8080b0",
    "STEP":  "#6c47f5",
    "WARN":  "#f0a030",
    "ERROR": "#e05050",
}
_LOG_BG = {
    "STEP":  "#18143a",
    "WARN":  "#2a1800",
    "ERROR": "#2a0d0d",
}

class ConsolePage(tk.Frame):
    """Live scrolling log console. Subscribes to the global AppLogger."""

    def __init__(self, parent, root: tk.Tk, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._root    = root
        self._paused  = False
        self._buf: list[tuple] = []   # buffered while paused
        self._filter  = "ALL"
        self._build()
        # Subscribe to logger — callback arrives on any thread, dispatch to UI
        from core.logger import log
        self._log_cb = lambda ts, lv, msg: root.after(
            0, lambda t=ts, l=lv, m=msg: self._append(t, l, m))
        log.subscribe(self._log_cb)

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 10))
        tk.Label(hdr, text="Console", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(hdr, text="  Live log — all app activity",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(
                     side="left", pady=(5, 0))
        _sep(self).pack(fill="x", padx=24)

        # Toolbar
        tb = tk.Frame(self, bg=BG)
        tb.pack(fill="x", padx=24, pady=(8, 0))

        # Level filter buttons
        tk.Label(tb, text="Level:", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._filt_btns: dict[str, tk.Button] = {}
        for lv in ["ALL", "STEP", "INFO", "WARN", "ERROR"]:
            col  = _LOG_COLORS.get(lv, TEXT2)
            is_a = lv == "ALL"
            b = tk.Button(tb, text=lv,
                          bg=ACCENT if is_a else CARD,
                          fg="white" if is_a else col,
                          relief="flat", font=("Segoe UI", 8, "bold"),
                          padx=8, pady=3, cursor="hand2",
                          command=lambda l=lv: self._set_filter(l))
            b.pack(side="left", padx=(0, 3))
            self._filt_btns[lv] = b

        # Right-side controls
        _btn(tb, "⏸  Pause Scroll", self._toggle_pause,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=4).pack(side="right", padx=(6, 0))
        self._pause_btn = tb.winfo_children()[-1]

        _btn(tb, "📋  Copy All", self._copy_all,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=4).pack(side="right", padx=(6, 0))

        _btn(tb, "🗑  Clear", self._clear,
             bg=CARD, fg=TEXT2, hover=CARD_HVR,
             font=("Segoe UI", 9), padx=10, pady=4).pack(side="right")

        # Log text widget
        log_f = tk.Frame(self, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        log_f.pack(fill="both", expand=True, padx=24, pady=(8, 0))

        self._txt = tk.Text(
            log_f, bg=CARD, fg=TEXT2, font=("Consolas", 9),
            relief="flat", bd=0, state="disabled", wrap="word",
            selectbackground=ACCENT, selectforeground=TEXT,
            padx=8, pady=6)
        sb = ttk.Scrollbar(log_f, command=self._txt.yview)
        self._txt.configure(yscrollcommand=sb.set)
        self._txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Configure colour tags
        for lv, col in _LOG_COLORS.items():
            self._txt.tag_configure(f"lv_{lv}", foreground=col)
            if lv in _LOG_BG:
                self._txt.tag_configure(f"lv_{lv}",
                                         foreground=col,
                                         background=_LOG_BG[lv])
        self._txt.tag_configure("ts",   foreground=TEXT3, font=("Consolas", 8))
        self._txt.tag_configure("dim",  foreground=TEXT3)

        # Entry count
        self._count_v = tk.StringVar(value="0 entries")
        tk.Label(self, textvariable=self._count_v,
                 bg=BG, fg=TEXT3, font=("Segoe UI", 9),
                 anchor="e").pack(fill="x", padx=26, pady=(3, 8))

        self._entry_count = 0

    def _append(self, ts: str, level: str, msg: str):
        if self._paused:
            self._buf.append((ts, level, msg))
            return
        if (self._filter != "ALL"
                and level != self._filter
                and not (self._filter == "WARN" and level == "ERROR")):
            return
        self._write(ts, level, msg)

    def _write(self, ts: str, level: str, msg: str):
        self._txt.configure(state="normal")
        tag = f"lv_{level}"
        pad = "  " if level in ("INFO", "WARN") else " " if level == "STEP" else "   "
        self._txt.insert("end", f"{ts} ", "ts")
        self._txt.insert("end", f"{level:5s}", tag)
        self._txt.insert("end", f"{pad}{msg}\n", tag)
        self._txt.configure(state="disabled")
        self._txt.see("end")
        self._entry_count += 1
        self._count_v.set(f"{self._entry_count} entries")

    def _set_filter(self, lv: str):
        self._filter = lv
        for k, b in self._filt_btns.items():
            b.configure(bg=ACCENT if k == lv else CARD,
                        fg="white" if k == lv else _LOG_COLORS.get(k, TEXT2))
        # Redraw from history
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")
        self._entry_count = 0
        from core.logger import log as applog
        for ts, level, msg in applog.all_entries():
            if (lv == "ALL" or level == lv
                    or (lv == "WARN" and level == "ERROR")):
                self._write(ts, level, msg)

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="▶  Resume Scroll", bg=WARNING_B, fg=WARNING)
        else:
            self._pause_btn.configure(text="⏸  Pause Scroll", bg=CARD, fg=TEXT2)
            for ts, lv, msg in self._buf:
                self._write(ts, lv, msg)
            self._buf.clear()

    def _clear(self):
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")
        self._entry_count = 0
        self._count_v.set("0 entries")

    def _copy_all(self):
        content = self._txt.get("1.0", "end")
        self._root.clipboard_clear()
        self._root.clipboard_append(content)


class App:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._cfg  = CFG.load()

        root.title(f"LocalTTS v{APP_VERSION}  –  Kokoro TTS")
        root.configure(bg=BG)
        root.minsize(920, 620)
        root.geometry("1150x750")
        apply(root)
        log.step(f"LocalTTS v{APP_VERSION} starting up")
        log.info(f"Python {__import__('sys').version.split()[0]}  |  "
                 f"Platform: {__import__('sys').platform}")

        self._qm = QueueManager(lambda fn: root.after(0, fn))
        self._qm.on("queued",    self._on_queued)
        self._qm.on("started",   self._on_started)
        self._qm.on("progress",  self._on_progress)
        self._qm.on("completed", self._on_completed)
        self._qm.on("failed",    self._on_failed)
        self._qm.on("cancelled", self._on_cancelled)
        self._qm.on("exhausted", self._on_exhausted)
        self._qm.on("pausing",   lambda: self._on_pause_state("pausing"))
        self._qm.on("paused",    lambda: self._on_pause_state("paused"))
        self._qm.on("resumed",   lambda: self._on_pause_state("running"))

        self._current = ""
        self._build()
        self._sidebar.select("synthesize")
        root.protocol("WM_DELETE_WINDOW", self._close)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self._root, bg=BG)
        outer.pack(fill="both", expand=True)

        self._sidebar = Sidebar(outer, on_select=self._show_page)
        self._sidebar.pack(side="left", fill="y")

        right = tk.Frame(outer, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._content = tk.Frame(right, bg=BG)
        self._content.pack(fill="both", expand=True)

        # ── Status bar ────────────────────────────────────────────────
        sb = tk.Frame(right, bg=SURFACE, height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_v = tk.StringVar(
            value="Ready  –  Voice model downloads automatically on first synthesis.")
        tk.Label(sb, textvariable=self._status_v,
                 bg=SURFACE, fg=TEXT3, font=("Segoe UI", 9),
                 anchor="w").pack(side="left", padx=12, pady=4)
        self._time_v = tk.StringVar()
        tk.Label(sb, textvariable=self._time_v,
                 bg=SURFACE, fg=TEXT3, font=("Segoe UI", 9),
                 anchor="e").pack(side="right", padx=12)
        self._tick_clock()

        # ── Pages ─────────────────────────────────────────────────────
        self._synth    = SynthesizePage(
            self._content, self._cfg, self._qm,
            on_status=self._status, on_navigate=self._show_page)
        self._qpage    = QueuePage(self._content, self._qm, self._status)
        self._vpage    = VoicesPage(self._content, self._cfg, self._on_voice_selected)
        self._hpage    = HistoryPage(self._content)
        self._console  = ConsolePage(self._content, self._root)
        self._spage    = SettingsPage(self._content, self._cfg, self._on_settings_sync)

        self._pages = {
            "synthesize": self._synth,
            "queue":      self._qpage,
            "voices":     self._vpage,
            "history":    self._hpage,
            "console":    self._console,
            "settings":   self._spage,
        }

    def _tick_clock(self):
        self._time_v.set(datetime.now().strftime("%H:%M:%S"))
        self._root.after(1000, self._tick_clock)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_page(self, name: str):
        if self._current:
            self._pages[self._current].pack_forget()
        self._pages[name].pack(fill="both", expand=True)
        self._current = name
        if name == "voices":   self._vpage.refresh()
        if name == "settings": self._spage.refresh()
        self._root.title(
            f"LocalTTS v{APP_VERSION}  –  {name.capitalize()}")

    # ── Queue event handlers ──────────────────────────────────────────────────

    def _on_queued(self, job: TTSJob):
        log.info(f"UI: Job {job.job_id} added to queue — '{job.preview[:40]}'")
        self._qpage.on_queued(job)
        n = self._qm.pending_count()
        self._sidebar.set_badge("queue", n)
        self._root.title(
            f"LocalTTS – {n} job{'s' if n != 1 else ''} pending")
        self._sidebar.set_engine_status("Queued", WARNING)

    def _on_started(self, jid: str):
        self._qpage.on_started(jid)
        self._status(f"⚙  Processing {jid}…")
        self._sidebar.set_engine_status("Running", SUCCESS)

    def _on_progress(self, jid: str, msg: str):
        self._qpage.on_progress(jid, msg)

    def _on_completed(self, jid: str, path: str):
        log.step(f"UI: Job {jid} completed → {path}")
        self._qpage.on_completed(jid, path)
        n = self._qm.pending_count()
        self._sidebar.set_badge("queue", n if n > 0 else 0)
        fname = Path(path).name
        self._status(f"✓  {jid} done  →  {fname}")

        job = self._qm._jobs.get(jid)
        if job:
            self._hpage.add_entry(job)

        if self._cfg.get("show_notifications", True):
            Toast(self._root, f"✓  {jid}  complete\n{fname}",
                  bg=SUCCESS_B, fg=SUCCESS_L)

        if self._cfg.get("auto_open_output", False):
            _open_path(str(Path(path).parent))

        if self._cfg.get("auto_clear_done", False):
            self._root.after(2000, lambda: self._qpage._clear_finished())

    def _on_failed(self, jid: str, err: str):
        log.error(f"UI: Job {jid} failed — {err}")
        self._qpage.on_failed(jid, err)
        n = self._qm.pending_count()
        self._sidebar.set_badge("queue", n if n > 0 else 0)
        self._status(f"✗  {jid} failed: {err[:80]}")
        if self._cfg.get("show_notifications", True):
            Toast(self._root, f"✗  Job {jid} failed\n{err[:60]}",
                  bg=ERROR_B, fg=ERROR_L)

    def _on_cancelled(self, jid: str):
        log.info(f"UI: Job {jid} cancelled")
        self._qpage.on_cancelled(jid)
        n = self._qm.pending_count()
        self._sidebar.set_badge("queue", n if n > 0 else 0)
        self._status(f"✕  Job {jid} cancelled")

    def _on_exhausted(self):
        self._sidebar.set_badge("queue", 0)
        self._sidebar.set_engine_status("Idle", TEXT3)
        self._status("✓  All jobs finished.")

    def _on_pause_state(self, state: str):
        self._qpage.update_pause_btn(state)
        if state == "paused":
            self._sidebar.set_engine_status("Paused", PAUSED_C)
            self._status("⏸  Queue paused — click Resume to continue.")
        elif state == "pausing":
            self._sidebar.set_engine_status("Pausing…", WARNING)
            self._status("⏸  Finishing current job, then pausing…")
        else:
            self._sidebar.set_engine_status("Running", SUCCESS)
            self._status("▶  Queue resumed.")

    # ── Cross-page sync ───────────────────────────────────────────────────────

    def _on_voice_selected(self, name: str):
        self._synth.set_voice(name)
        self._status(f"Voice → {name}")

    def _on_settings_sync(self):
        self._synth.set_voice(self._cfg.get("voice", ""))
        self._synth.sync_speed(float(self._cfg.get("speed", 1.0)))

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_v.set(msg)

    def _close(self):
        if self._qm.pending_count() > 0:
            if not messagebox.askyesno(
                "Jobs still running",
                "There are jobs still in the queue.\nQuit anyway and discard them?"):
                return
        self._qm.shutdown()
        self._root.quit()
        self._root.destroy()
