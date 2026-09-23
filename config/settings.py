"""config/settings.py – Kokoro voice catalogue and persisted settings."""
import json
from pathlib import Path

APP_VERSION       = "3.1"
CONFIG_DIR        = Path.home() / ".config" / "localtts"
CONFIG_FILE       = CONFIG_DIR / "settings.json"
DEFAULT_OUTPUT_DIR = Path.home() / "tts_output"

# Kokoro model files are stored here after download
MODEL_DIR  = CONFIG_DIR / "models"
MODEL_FILE = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_FILE= MODEL_DIR / "voices-v1.0.bin"

MODEL_DOWNLOAD_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_DOWNLOAD_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

SAMPLE_RATE = 24000   # Kokoro native sample rate

# ── Voice catalogue ──────────────────────────────────────────────────────────
# Kokoro-82M voices (Apache 2.0).  These are the voices bundled in voices-v1.0.bin
# lang: "en-us" = American English, "en-gb" = British English
VOICE_CATALOGUE: dict[str, dict] = {
    # ── American Female ───────────────────────────────────────────────────────
    "Heart  ·  American Female":   {"id":"af_heart",   "lang":"en-us","gender":"female","desc":"Warm, expressive — great for storytelling & vlogs"},
    "Bella  ·  American Female":   {"id":"af_bella",   "lang":"en-us","gender":"female","desc":"Friendly and upbeat — ideal for social media content"},
    "Sarah  ·  American Female":   {"id":"af_sarah",   "lang":"en-us","gender":"female","desc":"Clear, professional — podcasts & presentations"},
    "Sky    ·  American Female":   {"id":"af_sky",     "lang":"en-us","gender":"female","desc":"Bright and energetic — ads & promos"},
    "Nicole ·  American Female":   {"id":"af_nicole",  "lang":"en-us","gender":"female","desc":"Calm and natural — meditation & narration"},
    "Aoede  ·  American Female":   {"id":"af_aoede",   "lang":"en-us","gender":"female","desc":"Smooth and emotive — audiobooks"},
    "Kore   ·  American Female":   {"id":"af_kore",    "lang":"en-us","gender":"female","desc":"Bright and crisp — YouTube shorts"},
    # ── American Male ─────────────────────────────────────────────────────────
    "Adam   ·  American Male":     {"id":"am_adam",    "lang":"en-us","gender":"male","desc":"Confident and authoritative — news & documentaries"},
    "Michael·  American Male":     {"id":"am_michael", "lang":"en-us","gender":"male","desc":"Warm and engaging — podcasts & tutorials"},
    "Fenrir ·  American Male":     {"id":"am_fenrir",  "lang":"en-us","gender":"male","desc":"Deep and dramatic — trailers & promos"},
    "Puck   ·  American Male":     {"id":"am_puck",    "lang":"en-us","gender":"male","desc":"Playful and casual — gaming & entertainment"},
    "Echo   ·  American Male":     {"id":"am_echo",    "lang":"en-us","gender":"male","desc":"Clear and neutral — explainers & tutorials"},
    # ── British Female ────────────────────────────────────────────────────────
    "Emma   ·  British Female":    {"id":"bf_emma",    "lang":"en-gb","gender":"female","desc":"Elegant and refined — luxury & lifestyle content"},
    "Isabella· British Female":    {"id":"bf_isabella","lang":"en-gb","gender":"female","desc":"Sophisticated and clear — brand narration"},
    "Alice  ·  British Female":    {"id":"bf_alice",   "lang":"en-gb","gender":"female","desc":"Crisp BBC-style delivery — news & education"},
    # ── British Male ──────────────────────────────────────────────────────────
    "George ·  British Male":      {"id":"bm_george",  "lang":"en-gb","gender":"male","desc":"Classic British authority — docs & corporate"},
    "Lewis  ·  British Male":      {"id":"bm_lewis",   "lang":"en-gb","gender":"male","desc":"Conversational and modern — social media"},
    "Daniel ·  British Male":      {"id":"bm_daniel",  "lang":"en-gb","gender":"male","desc":"Calm and measured — narration & audiobooks"},
}

DEFAULT_VOICE    = "Heart  ·  American Female"
CHUNK_CHAR_LIMIT = 300   # Kokoro handles longer chunks well

DEFAULTS: dict = {
    "output_dir":        str(DEFAULT_OUTPUT_DIR),
    "voice":             DEFAULT_VOICE,
    "speed":             1.0,
    "chunk_limit":       CHUNK_CHAR_LIMIT,
    "auto_open_output":  False,
    "auto_clear_done":   False,
    "show_notifications":True,
    "output_template":   "{name}_{ts}",
}

def load() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **saved}
        except Exception:
            pass
    return dict(DEFAULTS)

def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
