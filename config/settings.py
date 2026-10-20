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

    # ── ElevenLabs (Neural High-Fidelity & Cloned Voices) ─────────────────────
    "Rachel ·  ElevenLabs (Female)":        {"id": "21m00Tcm4TlvDq8ikWAM", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Calm, warm American female — great for narration"},
    "Adam   ·  ElevenLabs (Male)":          {"id": "pNInz6obpgDQGcFmaJgB", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Deep, confident American male — narration & documentaries"},
    "Antoni ·  ElevenLabs (Male)":          {"id": "ErXwobaYiN019PkySvjV", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Well-rounded, smooth American male voice"},
    "Bella  ·  ElevenLabs (Female)":        {"id": "EXAVITQu4vr4xnSDxMaL", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Bright, expressive American female voice"},
    "Charlie·  ElevenLabs (Male)":          {"id": "IKne3meq5aSn9XLyUdCD", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Casual, conversational Australian male"},
    "Domi   ·  ElevenLabs (Female)":        {"id": "AZnzlk1XvdvUeBnXmlld", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Strong, engaging American female voice"},
    "Elli   ·  ElevenLabs (Female)":        {"id": "MF3mGyEYCl7XYWbV9V6O", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Emotional, expressive American female voice"},
    "Josh   ·  ElevenLabs (Male)":          {"id": "TxGEqnHWrfWFTfGW9XjX", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Deep, authoritative American male voice"},
    "Sam    ·  ElevenLabs (Male)":          {"id": "yoZ06aMxZJJ28mfd3POQ", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Dynamic, raspy American male voice"},
    "Jonathan - Professional, Calm, Credible, Clear  ·  ElevenLabs (Male)": {"id": "oyxaSt75JW8l04MCJaSo", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Warm, confident, credible technical explainer"},
    "George - Warm, Captivating Storyteller  ·  ElevenLabs (Male)": {"id": "JBFqnCBsd6RMkjVDRZzb", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Warm British resonance that captivates listeners"},
    "Johnny - authentic and expressive  ·  ElevenLabs (Male)": {"id": "S3jSeCD6zxApO2SHREet", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Authentic, friendly casual storyteller for explainers"},
    "Laura - Enthusiast, Quirky Attitude  ·  ElevenLabs (Female)": {"id": "FGY2WhTYpPnrIDTdsKH5", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Sunny enthusiasm with quirky energy"},
    "Sarah - Mature, Reassuring, Confident  ·  ElevenLabs (Female)": {"id": "EXAVITQu4vr4xnSDxMaL", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Confident, mature, reassuring delivery"},
    "Roger - Laid-Back, Casual, Resonant  ·  ElevenLabs (Male)": {"id": "CwhRBWXzGAHq8TQ4Fs17", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Laid-back, casual, resonant pacing"},
    "Steve  ·  ElevenLabs (Male)":          {"id": "s7VgmkAoDwT6l2zXqEPV", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Raspy British voice with counterculture grit"},
    "Jeremy - Young, Confident, American Male  ·  ElevenLabs (Male)": {"id": "bkWmSiLbVbuhntmf2Kw7", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Young, confident American male for financial explainers"},
    "Mother - Strong, Warm, Calm  ·  ElevenLabs (Female)": {"id": "TLeBnGDqmcwGf936zZyW", "lang": "multilingual", "gender": "female", "backend": "elevenlabs", "desc": "Deep, calm authority with gentle grit"},
    "Don Kim  ·  ElevenLabs (Male)":        {"id": "UI9arZeSp7bIUhGbx36K", "lang": "multilingual", "gender": "male",   "backend": "elevenlabs", "desc": "Calm, slightly raspy narrative tone"},
    "Michael C. Vincent  ·  ElevenLabs (Male)": {"id": "uju3wxzG5OhpWcoi3SMy", "lang": "multilingual", "gender": "male", "backend": "elevenlabs", "desc": "Warm bass tones, crisp clarity, articulate storytelling"},
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
    "elevenlabs_api_keys": [],
    "elevenlabs_model_id": "eleven_multilingual_v2",
    "elevenlabs_cached_voices": {},
}

def resolve_voice(voice_input: str, default: str = DEFAULT_VOICE) -> str:
    """
    Resolve any voice string (voice ID, full catalog name, short name, or alias)
    to a valid key in VOICE_CATALOGUE.
    Falls back to `default` if no match is found.
    """
    if not voice_input or not isinstance(voice_input, str):
        return default

    v_clean = voice_input.strip()
    if not v_clean:
        return default

    # 1. Exact match in catalogue keys
    if v_clean in VOICE_CATALOGUE:
        return v_clean

    v_lower = v_clean.lower()

    # 2. Match against voice ID (e.g. "am_adam", "af_heart", "pt_BR-faber-medium")
    for name, cfg in VOICE_CATALOGUE.items():
        if cfg.get("id", "").lower() == v_lower:
            return name

    # 3. Match against key case-insensitively or with normalized spacing
    v_normalized = " ".join(v_lower.replace("·", " ").split())
    for name in VOICE_CATALOGUE:
        name_norm = " ".join(name.lower().replace("·", " ").split())
        if name_norm == v_normalized:
            return name

    # 4. Match short name (e.g. "Adam", "Heart", "Bella") before dot or space
    for name, cfg in VOICE_CATALOGUE.items():
        short_name = name.split("·")[0].strip().lower()
        if short_name == v_lower or short_name == v_lower.split("·")[0].strip():
            return name

    # 5. Partial match in voice ID or name
    for name, cfg in VOICE_CATALOGUE.items():
        if v_lower in cfg.get("id", "").lower() or v_lower in name.lower():
            return name

    # 6. Legacy/external alias mapping
    aliases = {
        "en_us_male_dry_narrator": "Adam   ·  American Male",
        "en_us_female_narrator": "Heart  ·  American Female",
    }
    if v_lower in aliases:
        return aliases[v_lower]

    return default


def extract_voice_from_meta(meta: dict, default_voice: str = DEFAULT_VOICE) -> str:
    """
    Extract and resolve the target TTS voice from project metadata.
    Checks voice_name, voice_id, voice, tts_voice, speaker, speaker_voice, preset_name.
    """
    if not isinstance(meta, dict):
        return default_voice

    raw_voice = (
        meta.get("voice_name")
        or meta.get("voice_id")
        or meta.get("voice")
        or meta.get("tts_voice")
        or meta.get("speaker")
        or meta.get("speaker_voice")
    )

    if raw_voice:
        resolved = resolve_voice(str(raw_voice), default=default_voice)
        if resolved:
            return resolved

    preset_name = meta.get("preset_name")
    if preset_name:
        registry_path = Path("H:/Automation/Presets/master_presets_registry.json")
        if not registry_path.exists():
            registry_path = Path(__file__).resolve().parent.parent.parent / "Presets" / "master_presets_registry.json"
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8-sig"))
                preset_info = data.get(preset_name, {})
                use_el = (
                    meta.get("use_elevenlabs")
                    or meta.get("backend") == "elevenlabs"
                    or meta.get("voice_backend") == "elevenlabs"
                )
                if use_el and preset_info.get("elevenlabs_voice"):
                    return resolve_voice(str(preset_info.get("elevenlabs_voice")), default=default_voice)
                preset_voice = (
                    preset_info.get("offline_voice")
                    or preset_info.get("voice_name")
                    or preset_info.get("voice_id")
                    or preset_info.get("elevenlabs_voice")
                )
                if preset_voice:
                    return resolve_voice(str(preset_voice), default=default_voice)
            except Exception:
                pass

    return default_voice


def sync_elevenlabs_voices(cached_voices: dict = None) -> None:
    """
    Merge cached or newly fetched ElevenLabs voices into VOICE_CATALOGUE in-place.
    """
    if cached_voices is None:
        try:
            cfg = load()
            cached_voices = cfg.get("elevenlabs_cached_voices", {})
        except Exception:
            cached_voices = {}

    if not isinstance(cached_voices, dict):
        return

    for cat_name, info in cached_voices.items():
        if isinstance(info, dict) and info.get("id"):
            VOICE_CATALOGUE[cat_name] = {
                "id": str(info.get("id", "")).strip(),
                "name": str(info.get("name", cat_name)).strip(),
                "lang": str(info.get("lang", "multilingual")),
                "gender": str(info.get("gender", "neutral")),
                "backend": "elevenlabs",
                "desc": str(info.get("desc", "ElevenLabs Voice")),
                "category": str(info.get("category", "premade")),
                "preview_url": str(info.get("preview_url", "")),
            }


def load() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = {**DEFAULTS, **saved}
        except Exception:
            pass
    # Automatically ensure cached voices are in VOICE_CATALOGUE
    sync_elevenlabs_voices(cfg.get("elevenlabs_cached_voices", {}))
    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    if "elevenlabs_cached_voices" in cfg:
        sync_elevenlabs_voices(cfg.get("elevenlabs_cached_voices", {}))

# Load any existing cached voices on import
try:
    sync_elevenlabs_voices()
except Exception:
    pass

