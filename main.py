"""
LocalTTS v3 – entry point.
Run:  python main.py
"""
import os, sys

# Patch sys.path FIRST so all sub-packages resolve regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main():
    import tkinter as tk
    from ui.dep_check import StartupDialog

    root = tk.Tk()
    root.withdraw()

    def on_ready():
        root.deiconify()
        from ui.app import App
        App(root)

    StartupDialog(root, on_ready)
    root.mainloop()


if __name__ == "__main__":
    main()
