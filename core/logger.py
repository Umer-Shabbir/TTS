"""
core/logger.py – App-wide logging hub.

Usage anywhere in the codebase:
    from core.logger import log
    log.info("Something happened")
    log.warn("Possible issue")
    log.error("Something broke")
    log.debug("Low-level detail")
    log.step("Major pipeline step")   # highlighted

The Console page subscribes via log.subscribe(callback).
Callbacks receive (level, message, timestamp) on whatever thread they are
called from — the Console page always dispatches to the UI thread via root.after.

All entries are also written to  ~/.config/localtts/app.log  so they
survive session restarts and can be inspected externally.
"""

import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Tuple

# Log file location
_LOG_FILE = Path.home() / ".config" / "localtts" / "app.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_LEVELS = {"DEBUG", "INFO", "STEP", "WARN", "ERROR"}


class AppLogger:
    def __init__(self):
        self._lock       = threading.Lock()
        self._entries:   List[Tuple[str, str, str]] = []  # (ts, level, msg)
        self._callbacks: List[Callable] = []
        self._fh         = None
        try:
            self._fh = open(_LOG_FILE, "a", encoding="utf-8", buffering=1)
            self._fh.write(f"\n{'='*60}\n"
                           f"Session started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                           f"{'='*60}\n")
        except Exception:
            pass

    # ── Public logging API ────────────────────────────────────────────────────

    def debug(self, msg: str): self._log("DEBUG", msg)
    def info (self, msg: str): self._log("INFO",  msg)
    def step (self, msg: str): self._log("STEP",  msg)
    def warn (self, msg: str): self._log("WARN",  msg)
    def error(self, msg: str): self._log("ERROR", msg)

    def exception(self, msg: str):
        """Log an error with the current exception traceback."""
        tb = traceback.format_exc()
        self._log("ERROR", f"{msg}\n{tb.strip()}")

    # ── Subscription ─────────────────────────────────────────────────────────

    def subscribe(self, cb: Callable) -> None:
        """cb(ts: str, level: str, msg: str) — called for every new entry."""
        with self._lock:
            self._callbacks.append(cb)
            # Replay existing entries so the Console shows history on open
            entries = list(self._entries)
        for ts, lv, m in entries:
            cb(ts, lv, m)

    def unsubscribe(self, cb: Callable) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not cb]

    def shutdown(self) -> None:
        """Flushes file stream, closes file handle, and clears callbacks."""
        with self._lock:
            self._callbacks.clear()
            if self._fh:
                try:
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self._fh.write(f"[{ts}] INFO   Session closed gracefully\n{'='*60}\n")
                    self._fh.flush()
                    self._fh.close()
                except Exception:
                    pass
                finally:
                    self._fh = None

    close = shutdown  # alias

    def all_entries(self) -> List[Tuple[str, str, str]]:
        with self._lock:
            return list(self._entries)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self._lock:
            self._entries.append((ts, level, msg))
            if len(self._entries) > 2000:   # cap in-memory buffer
                self._entries = self._entries[-1500:]
            cbs = list(self._callbacks)
        # Write to file
        if self._fh:
            try:
                self._fh.write(f"[{ts}] {level:5s}  {msg}\n")
            except Exception:
                pass
        # Notify subscribers
        for cb in cbs:
            try:
                cb(ts, level, msg)
            except Exception:
                pass


# Singleton
log = AppLogger()
