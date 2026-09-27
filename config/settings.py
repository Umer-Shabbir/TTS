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
# Multi-backend voices
# lang: "en-us" = American English, "en-gb" = British English
VOICE_CATALOGUE: dict[str, dict] = {
    # ── Kokoro (Offline, High Quality English) ───────────────────────────────
    "Heart  ·  American Female":   {"id":"af_heart",   "lang":"en-us","gender":"female","backend":"kokoro","desc":"Warm, expressive — great for storytelling & vlogs"},
    "Bella  ·  American Female":   {"id":"af_bella",   "lang":"en-us","gender":"female","backend":"kokoro","desc":"Friendly and upbeat — ideal for social media content"},
    "Sarah  ·  American Female":   {"id":"af_sarah",   "lang":"en-us","gender":"female","backend":"kokoro","desc":"Clear, professional — podcasts & presentations"},
    "Sky    ·  American Female":   {"id":"af_sky",     "lang":"en-us","gender":"female","backend":"kokoro","desc":"Bright and energetic — ads & promos"},
    "Nicole ·  American Female":   {"id":"af_nicole",  "lang":"en-us","gender":"female","backend":"kokoro","desc":"Calm and natural — meditation & narration"},
    "Aoede  ·  American Female":   {"id":"af_aoede",   "lang":"en-us","gender":"female","backend":"kokoro","desc":"Smooth and emotive — audiobooks"},
    "Kore   ·  American Female":   {"id":"af_kore",    "lang":"en-us","gender":"female","backend":"kokoro","desc":"Bright and crisp — YouTube shorts"},
    "Adam   ·  American Male":     {"id":"am_adam",    "lang":"en-us","gender":"male","backend":"kokoro","desc":"Confident and authoritative — news & documentaries"},
    "Michael·  American Male":     {"id":"am_michael", "lang":"en-us","gender":"male","backend":"kokoro","desc":"Warm and engaging — podcasts & tutorials"},
    "Fenrir ·  American Male":     {"id":"am_fenrir",  "lang":"en-us","gender":"male","backend":"kokoro","desc":"Deep and dramatic — trailers & promos"},
    "Puck   ·  American Male":     {"id":"am_puck",    "lang":"en-us","gender":"male","backend":"kokoro","desc":"Playful and casual — gaming & entertainment"},
    "Echo   ·  American Male":     {"id":"am_echo",    "lang":"en-us","gender":"male","backend":"kokoro","desc":"Clear and neutral — explainers & tutorials"},
    "Emma   ·  British Female":    {"id":"bf_emma",    "lang":"en-gb","gender":"female","backend":"kokoro","desc":"Elegant and refined — luxury & lifestyle content"},
    "Isabella· British Female":    {"id":"bf_isabella","lang":"en-gb","gender":"female","backend":"kokoro","desc":"Sophisticated and clear — brand narration"},
    "Alice  ·  British Female":    {"id":"bf_alice",   "lang":"en-gb","gender":"female","backend":"kokoro","desc":"Crisp BBC-style delivery — news & education"},
    "George ·  British Male":      {"id":"bm_george",  "lang":"en-gb","gender":"male","backend":"kokoro","desc":"Classic British authority — docs & corporate"},
    "Lewis  ·  British Male":      {"id":"bm_lewis",   "lang":"en-gb","gender":"male","backend":"kokoro","desc":"Conversational and modern — social media"},
    "Daniel ·  British Male":      {"id":"bm_daniel",  "lang":"en-gb","gender":"male","backend":"kokoro","desc":"Calm and measured — narration & audiobooks"},

    # ── Piper (Offline Multilingual) ──────────────────────────────────────────
    # format: pt_BR-faber-medium, ko_KR-kss-medium, zh_CN-huayan-medium, hi_IN-pratham-medium, ur_PK-aegis_female-medium
    "Faber  ·  Portuguese Male (Offline)": {
        "id": "pt_BR-faber-medium", "lang": "pt-br", "gender": "male", "backend": "piper",
        "desc": "Clear Brazilian Portuguese narration",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
    },
    "Tugao  ·  Portuguese Male (Offline)": {
        "id": "pt_PT-tugão-medium", "lang": "pt-pt", "gender": "male", "backend": "piper",
        "desc": "Traditional Portuguese accent",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_PT/tug%C3%A3o/medium/pt_PT-tug%C3%A3o-medium.onnx.json"
    },
    "KSS    ·  Korean Female (Offline)": {
        "id": "ko_KR-kss-medium", "lang": "ko-kr", "gender": "female", "backend": "piper",
        "desc": "Standard Korean female voice",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ko/ko_KR/kss/medium/ko_KR-kss-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ko/ko_KR/kss/medium/ko_KR-kss-medium.onnx.json"
    },
    "Huayan ·  Chinese Female (Offline)": {
        "id": "zh_CN-huayan-medium", "lang": "zh-cn", "gender": "female", "backend": "piper",
        "desc": "Natural Mandarin narration",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json"
    },
    "Pratham·  Hindi Male (Offline)": {
        "id": "hi_IN-pratham-medium", "lang": "hi-in", "gender": "male", "backend": "piper",
        "desc": "Clear Hindi male narration",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json"
    },
    "Priyamvada · Hindi Female (Offline)": {
        "id": "hi_IN-priyamvada-medium", "lang": "hi-in", "gender": "female", "backend": "piper",
        "desc": "Clear Hindi female narration voice",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json"
    },
    "Aegis  ·  Urdu Female (Offline)": {
        "id": "ur_PK-aegis_female-medium", "lang": "ur-pk", "gender": "female", "backend": "piper",
        "desc": "Pakistani Urdu female narration voice",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/aegis_female/medium/ur_PK-aegis_female-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/aegis_female/medium/ur_PK-aegis_female-medium.onnx.json"
    },
    "Fasih  ·  Urdu Male (Offline)": {
        "id": "ur_PK-fasih-medium", "lang": "ur-pk", "gender": "male", "backend": "piper",
        "desc": "Pakistani Urdu male narration voice",
        "url_onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/fasih/medium/ur_PK-fasih-medium.onnx",
        "url_json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/fasih/medium/ur_PK-fasih-medium.onnx.json"
    },

    # ── Edge-TTS (Online Multilingual) ───────────────────────────────────────
    "Antonio·  Portuguese Male (Online)":   {"id": "pt-BR-AntonioNeural", "lang": "pt-br", "gender": "male", "backend": "edgetts", "desc": "High quality Brazilian Portuguese (Online)"},
    "Francisca· Portuguese Female (Online)":{"id": "pt-BR-FranciscaNeural", "lang": "pt-br", "gender": "female", "backend": "edgetts", "desc": "High quality Brazilian Portuguese (Online)"},
    "InJoon ·  Korean Male (Online)":       {"id": "ko-KR-InJoonNeural", "lang": "ko-kr", "gender": "male", "backend": "edgetts", "desc": "Premium Korean Male (Online)"},
    "SunHi  ·  Korean Female (Online)":     {"id": "ko-KR-SunHiNeural", "lang": "ko-kr", "gender": "female", "backend": "edgetts", "desc": "Premium Korean Female (Online)"},
    "Yunxi  ·  Chinese Male (Online)":      {"id": "zh-CN-YunxiNeural", "lang": "zh-cn", "gender": "male", "backend": "edgetts", "desc": "Popular Chinese Male Narration (Online)"},
    "Xiaoxiao· Chinese Female (Online)":    {"id": "zh-CN-XiaoxiaoNeural", "lang": "zh-cn", "gender": "female", "backend": "edgetts", "desc": "Classic Chinese Female Voice (Online)"},
    "Madhur ·  Hindi Male (Online)":        {"id": "hi-IN-MadhurNeural", "lang": "hi-in", "gender": "male", "backend": "edgetts", "desc": "Premium Hindi Male (Online)"},
    "Swara  ·  Hindi Female (Online)":      {"id": "hi-IN-SwaraNeural", "lang": "hi-in", "gender": "female", "backend": "edgetts", "desc": "Premium Hindi Female (Online)"},
    "Asad   ·  Urdu Male (Online)":         {"id": "ur-PK-AsadNeural", "lang": "ur-pk", "gender": "male", "backend": "edgetts", "desc": "Pakistani Urdu Male (Online)"},
    "Uzma   ·  Urdu Female (Online)":       {"id": "ur-PK-UzmaNeural", "lang": "ur-pk", "gender": "female", "backend": "edgetts", "desc": "Pakistani Urdu Female (Online)"},
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
    "enhance_audio":     True,
    "smart_pacing":      True,
    "blend_voice_ratio": 0.0,
    "secondary_voice":   "",
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
