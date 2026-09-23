"""
ui/folder_paste_dialog.py – Paste project folder paths modal (Image Automation style).

Allows the user to paste absolute paths to project folders (one per line)
into a text area, exactly like the Image Automation tool.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import List, Optional

import ui.theme as T


class FolderPasteDialog:
    """
    Modal dialog for pasting project folder paths (one per line).
    """

    def __init__(self, parent: tk.Misc, title: str = "Add Project Folders"):
        self._parent = parent
        self._result: List[Path] = []

        win = self._w = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=T.BG)
        win.geometry("720x540")
        win.minsize(560, 420)
        win.resizable(True, True)
        win.transient(parent)
        win.grab_set()

        # Centre on screen
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = 720, 540
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._build()
        win.protocol("WM_DELETE_WINDOW", self._cancel)
        parent.wait_window(win)

    def _build(self):
        win = self._w

        # Header
        hdr = tk.Frame(win, bg=T.ACCENT, padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📁  Add Project Folders by Path",
                 bg=T.ACCENT, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        # Bottom Action Bar (placed first or packed properly so it's always visible)
        bot = tk.Frame(win, bg=T.SURFACE, padx=16, pady=12)
        bot.pack(fill="x", side="bottom")
        tk.Frame(win, bg=T.BORDER, height=1).pack(fill="x", side="bottom")

        self._mkbtn(bot, "Cancel", self._cancel,
                    bg=T.CARD, fg=T.TEXT2, hover=T.CARD_HVR, padx=16, pady=8).pack(side="right", padx=(8, 0))

        # Big Prominent Save & Add to Queue button
        self._mkbtn(bot, "💾 Save & Add to Queue", self._confirm,
                    bg=T.SUCCESS, fg="#051a10", hover=T.SUCCESS_L,
                    font=("Segoe UI", 11, "bold"), padx=20, pady=8).pack(side="right")

        tk.Label(bot, text="Paste one path per line", bg=T.SURFACE, fg=T.TEXT3,
                 font=("Segoe UI", 9)).pack(side="left")

        # Body
        body = tk.Frame(win, bg=T.BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text="Enter or paste absolute paths to project folders (one per line):\nEach folder must contain a script.txt file.",
            bg=T.BG, fg=T.TEXT2, font=("Segoe UI", 9), justify="left"
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Text area with border frame
        txt_frame = tk.Frame(body, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER2)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.rowconfigure(0, weight=1)
        txt_frame.columnconfigure(0, weight=1)

        self._text = tk.Text(
            txt_frame,
            bg=T.CARD, fg=T.TEXT,
            insertbackground=T.TEXT,
            selectbackground=T.ACCENT,
            selectforeground=T.TEXT,
            font=("Consolas", 10),
            relief="flat", bd=0,
            padx=10, pady=8, wrap="none",
        )
        vsb = ttk.Scrollbar(txt_frame, orient="vertical", command=self._text.yview)
        hsb = ttk.Scrollbar(txt_frame, orient="horizontal", command=self._text.xview)
        self._text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Example placeholder / tip
        self._text.insert("1.0", r"H:\Automation\output\project_alpha" + "\n" + r"H:\Automation\output\project_beta")
        self._text.tag_add("sel", "1.0", "end-1c")
        self._text.focus_set()

    @staticmethod
    def _mkbtn(parent, text, cmd, bg, fg, hover,
               font=("Segoe UI", 9, "bold"), padx=14, pady=6, **kw) -> tk.Button:
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg, font=font,
            relief="flat", bd=0, padx=padx, pady=pady,
            cursor="hand2",
            activebackground=hover, activeforeground=fg,
            **kw,
        )
        b.bind("<Enter>", lambda e: b.configure(bg=hover) if str(b.cget("state")) != "disabled" else None)
        b.bind("<Leave>", lambda e: b.configure(bg=bg) if str(b.cget("state")) != "disabled" else None)
        return b

    def _confirm(self):
        raw = self._text.get("1.0", "end")
        paths = []
        for line in raw.splitlines():
            cleaned = line.strip().strip('"').strip("'")
            if cleaned:
                p = Path(cleaned)
                if p.is_dir():
                    paths.append(p)
        self._result = paths
        self._w.grab_release()
        self._w.destroy()

    def _cancel(self):
        self._result = []
        self._w.grab_release()
        self._w.destroy()

    @property
    def result(self) -> List[Path]:
        return self._result


def ask_folders(parent: tk.Misc, title: str = "Add Project Folders", initial_dir: Optional[Path] = None) -> List[Path]:
    """
    Open the Image Automation style folder-path pasting dialog.
    Returns list of Path objects.
    """
    dlg = FolderPasteDialog(parent, title=title)
    return dlg.result
