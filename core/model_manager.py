"""
core/model_manager.py
─────────────────────
Downloads and caches Kokoro-82M ONNX model files and Piper models.

Files stored in: ~/.config/localtts/models/
  kokoro-v1.0.onnx   ~310 MB  (the neural network)
  voices-v1.0.bin    ~  6 MB  (voice embeddings for all speakers)
  piper/<voice_id>/  Piper ONNX voice and config files (~20-60 MB each)

Both files are downloaded once; subsequent runs use the local cache.
"""
import urllib.request
from pathlib import Path
from typing import Callable, Optional
from config.settings import MODEL_DIR, MODEL_FILE, VOICES_FILE
from config.settings import MODEL_DOWNLOAD_URL, VOICES_DOWNLOAD_URL
from core.logger import log


def models_cached() -> bool:
    """Return True only if both model files are fully present."""
    return MODEL_FILE.exists() and VOICES_FILE.exists() and \
           MODEL_FILE.stat().st_size > 1_000_000 and \
           VOICES_FILE.stat().st_size > 100_000


def _download_file(url: str, dest: Path,
                   label: str,
                   progress_cb: Optional[Callable[[str], None]] = None) -> bool:
    """Download *url* to *dest* with progress reporting. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LocalTTS/3.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            total_mb = total / 1024 / 1024 if total else 0
            downloaded = 0
            block = 1024 * 64   # 64 KB chunks

            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(block)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        done_mb = downloaded / 1024 / 1024
                        msg = f"{label}: {done_mb:.0f} / {total_mb:.0f} MB  ({pct:.0f}%)"
                    else:
                        msg = f"{label}: {downloaded/1024/1024:.0f} MB downloaded…"
                    if progress_cb:
                        progress_cb(msg)
                    log.debug(msg)

        # Rename tmp → final only on full success
        if tmp.exists():
            tmp.replace(dest)
        log.info(f"Downloaded {label} → {dest}")
        return True

    except Exception as e:
        log.error(f"Download failed for {label}: {e}")
        if tmp.exists():
            try: tmp.unlink()
            except OSError: pass
        return False


def ensure_models_downloaded(
    progress_cb: Optional[Callable[[str], None]] = None
) -> tuple[bool, str]:
    """
    Download Kokoro model files if not already cached.
    Returns (success: bool, error_message: str).
    """
    if models_cached():
        msg = "Kokoro model files already cached."
        log.info(msg)
        if progress_cb: progress_cb(msg)
        return True, ""

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    errors = []

    if not (VOICES_FILE.exists() and VOICES_FILE.stat().st_size > 100_000):
        log.step("Downloading voices-v1.0.bin (~6 MB)…")
        if progress_cb: progress_cb("Downloading voice embeddings (~6 MB)…")
        ok = _download_file(VOICES_DOWNLOAD_URL, VOICES_FILE,
                            "voices-v1.0.bin", progress_cb)
        if not ok:
            errors.append("voices-v1.0.bin download failed")

    if not (MODEL_FILE.exists() and MODEL_FILE.stat().st_size > 1_000_000):
        log.step("Downloading kokoro-v1.0.onnx (~310 MB)…")
        if progress_cb: progress_cb("Downloading Kokoro ONNX model (~310 MB)…")
        ok = _download_file(MODEL_DOWNLOAD_URL, MODEL_FILE,
                            "kokoro-v1.0.onnx", progress_cb)
        if not ok:
            errors.append("kokoro-v1.0.onnx download failed")

    if errors:
        err = "; ".join(errors)
        log.error(f"Model download incomplete: {err}")
        return False, err

    log.step("All Kokoro model files downloaded and cached.")
    if progress_cb: progress_cb("Model files ready.")
    return True, ""


def ensure_piper_voice_downloaded(
    voice_cfg: dict,
    progress_cb: Optional[Callable[[str], None]] = None
) -> tuple[bool, Path, Path]:
    """
    Ensure the given Piper voice model (.onnx and .onnx.json) is cached.
    Returns (success: bool, model_path: Path, config_path: Path).
    """
    voice_id = voice_cfg.get("id")
    url_onnx = voice_cfg.get("url_onnx")
    url_json = voice_cfg.get("url_json")

    if not voice_id or not url_onnx or not url_json:
        return False, Path(""), Path("")

    piper_dir = MODEL_DIR / "piper" / voice_id
    piper_dir.mkdir(parents=True, exist_ok=True)

    dest_onnx = piper_dir / f"{voice_id}.onnx"
    dest_json = piper_dir / f"{voice_id}.onnx.json"

    # Check if already present and non-empty
    if dest_onnx.exists() and dest_json.exists() and dest_onnx.stat().st_size > 10_000:
        return True, dest_onnx, dest_json

    log.step(f"Downloading Piper voice {voice_id}…")
    if progress_cb:
        progress_cb(f"Downloading {voice_id} config…")
    ok_json = _download_file(url_json, dest_json, f"{voice_id}.onnx.json", progress_cb)
    if not ok_json:
        return False, dest_onnx, dest_json

    if progress_cb:
        progress_cb(f"Downloading {voice_id} model…")
    ok_onnx = _download_file(url_onnx, dest_onnx, f"{voice_id}.onnx", progress_cb)
    if not ok_onnx:
        return False, dest_onnx, dest_json

    return True, dest_onnx, dest_json
