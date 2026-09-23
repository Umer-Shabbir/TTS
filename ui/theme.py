"""ui/theme.py – Colour palette, fonts, and ttk.Style configuration."""
import tkinter as tk
from tkinter import ttk

# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#0d0d1a"   # deep navy-black background
SURFACE   = "#13132a"   # sidebar / raised panel
CARD      = "#1a1a35"   # card background
CARD_HVR  = "#202040"   # card hover state
CARD_ACT  = "#252550"   # card active / pressed

BORDER    = "#252545"   # subtle borders
BORDER2   = "#353560"   # visible borders

TEXT      = "#e8e8ff"   # primary text
TEXT2     = "#8080b0"   # secondary / muted text
TEXT3     = "#404060"   # disabled / faint text

ACCENT    = "#6c47f5"   # main indigo accent
ACCENT_L  = "#8b6fff"   # lighter accent (hover)
ACCENT_D  = "#4d2fd4"   # darker accent (pressed)
ACCENT_BG = "#1a1040"   # accent tinted background

SUCCESS   = "#2ecc71"
SUCCESS_B = "#0d2a1a"
SUCCESS_L = "#4edd8a"

WARNING   = "#f0a030"
WARNING_B = "#2a1800"
WARNING_L = "#ffc060"

ERROR     = "#e05050"
ERROR_B   = "#2a0d0d"
ERROR_L   = "#ff7070"

INFO      = "#40b4f0"
INFO_B    = "#0a2030"

PAUSED_C  = "#c084fc"   # purple for paused state
PAUSED_B  = "#1e0a30"

NEUTRAL_B = "#1e1e3a"

FEMALE_BG  = "#22103a"; FEMALE_ACC = "#c084fc"
MALE_BG    = "#0e1e3a"; MALE_ACC   = "#60a5fa"
NEUTRAL_BG = "#102a20"; NEUTRAL_ACC= "#34d399"

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_SMALL  = ("Segoe UI",  9)
F_NORMAL = ("Segoe UI", 10)
F_BOLD   = ("Segoe UI", 10, "bold")
F_TITLE  = ("Segoe UI", 13, "bold")
F_H1     = ("Segoe UI", 18, "bold")
F_H2     = ("Segoe UI", 14, "bold")
F_MONO   = ("Consolas",  9)
F_BADGE  = ("Segoe UI",  8, "bold")
F_LABEL  = ("Segoe UI",  9, "bold")

# ── ttk Style ─────────────────────────────────────────────────────────────────
def apply(root: tk.Tk) -> None:
    s = ttk.Style(root)
    s.theme_use("clam")

    s.configure(".", background=BG, foreground=TEXT,
                 troughcolor=SURFACE, fieldbackground=CARD,
                 bordercolor=BORDER, selectbackground=ACCENT,
                 selectforeground=TEXT, font=F_NORMAL,
                 focuscolor=ACCENT)

    s.configure("TFrame",      background=BG)
    s.configure("Card.TFrame", background=CARD)

    s.configure("TLabel",         background=BG,    foreground=TEXT,  font=F_NORMAL)
    s.configure("Sub.TLabel",     background=BG,    foreground=TEXT2, font=F_SMALL)
    s.configure("Card.TLabel",    background=CARD,  foreground=TEXT,  font=F_NORMAL)
    s.configure("CardSub.TLabel", background=CARD,  foreground=TEXT2, font=F_SMALL)
    s.configure("Title.TLabel",   background=BG,    foreground=TEXT,  font=F_TITLE)

    s.configure("TScrollbar",
                background=BORDER, troughcolor=SURFACE,
                arrowcolor=TEXT3,  bordercolor=BG,
                gripcount=0, width=7, arrowsize=7)
    s.map("TScrollbar", background=[("active", BORDER2)])

    s.configure("TCombobox",
                fieldbackground=CARD, background=CARD,
                foreground=TEXT, arrowcolor=TEXT2,
                bordercolor=BORDER2, padding=6,
                selectbackground=ACCENT, selectforeground=TEXT)
    s.map("TCombobox",
          fieldbackground=[("readonly", CARD)],
          foreground=[("readonly", TEXT)],
          arrowcolor=[("disabled", TEXT3)])

    s.configure("TScale",
                background=BG, troughcolor=BORDER2,
                sliderlength=16, sliderrelief="flat",
                troughrelief="flat")
    s.map("TScale", background=[("active", ACCENT_L)])

    s.configure("TSeparator", background=BORDER)

    s.configure("TProgressbar",
                troughcolor=BORDER, background=ACCENT,
                bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT_D,
                thickness=4)

    # Combobox dropdown colours
    root.option_add("*TCombobox*Listbox.background",       CARD)
    root.option_add("*TCombobox*Listbox.foreground",       TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    root.option_add("*TCombobox*Listbox.font",             F_NORMAL)
    root.option_add("*TCombobox*Listbox.relief",           "flat")
