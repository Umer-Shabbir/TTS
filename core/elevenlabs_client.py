"""
core/elevenlabs_client.py – ElevenLabs API Client for LocalTTS.
Handles bulk API key validation, account subscription checks, voice catalog retrieval,
and high-fidelity audio synthesis with automatic key failover and quota tracking.
"""

import json
import os
import re
import tempfile
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from core.logger import log

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"

ELEVENLABS_MODELS = [
    ("eleven_multilingual_v2", "Eleven Multilingual v2 (Best Quality, 29 Languages)"),
    ("eleven_flash_v2_5",      "Eleven Flash v2.5 (Fastest & Lowest Cost)"),
    ("eleven_turbo_v2_5",      "Eleven Turbo v2.5 (High Speed & Quality)"),
    ("eleven_monolingual_v1",   "Eleven Monolingual v1 (English Legacy)"),
]

DEFAULT_MODEL_ID = "eleven_multilingual_v2"


def _create_ssl_context():
    """Create a permissive SSL context for environments with custom certificates."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        return None


def mask_key(key: str) -> str:
    """Mask an API key for safe display (e.g. sk_12...9a)."""
    if not key or not isinstance(key, str):
        return ""
    key = key.strip()
    if len(key) <= 8:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def parse_bulk_keys(text: str) -> List[str]:
    """
    Parse a raw string containing one or more ElevenLabs API keys.
    Supports delimiters: newlines, commas, semicolons, whitespace.
    Ignores blank lines and comments starting with '#' or '//'.
    Returns deduplicated list of non-empty keys preserving insertion order.
    """
    if not text or not isinstance(text, str):
        return []

    raw_tokens = re.split(r'[\r\n,;]+', text)
    cleaned_keys: List[str] = []
    seen = set()

    for token in raw_tokens:
        tok = token.strip()
        # Strip wrapping quotes if any
        tok = tok.strip('"\'`')
        # Skip empty lines or comment lines
        if not tok or tok.startswith("#") or tok.startswith("//"):
            continue
        # Split by spaces if multiple keys on same line
        parts = [p.strip('"\'`') for p in tok.split() if p.strip()]
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned_keys.append(p)

    return cleaned_keys


def validate_api_key(api_key: str, timeout: float = 10.0) -> dict:
    """
    Validate an ElevenLabs API key against the official subscription API.
    Endpoint: GET https://api.elevenlabs.io/v1/user/subscription

    Returns a standardized dictionary:
    {
        "valid": bool,
        "key": str,
        "masked": str,
        "tier": str,
        "character_count": int,
        "character_limit": int,
        "characters_left": int,
        "status": str,
        "message": str,
        "checked_at": str (ISO timestamp)
    }
    """
    api_key = (api_key or "").strip()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not api_key:
        return {
            "valid": False,
            "key": "",
            "masked": "",
            "tier": "unknown",
            "character_count": 0,
            "character_limit": 0,
            "characters_left": 0,
            "status": "empty",
            "message": "API key cannot be empty.",
            "checked_at": now_iso
        }

    masked = mask_key(api_key)
    url = f"{ELEVENLABS_API_BASE}/user/subscription"
    req = urllib.request.Request(
        url,
        headers={
            "xi-api-key": api_key,
            "User-Agent": "LocalTTS/3.1"
        },
        method="GET"
    )

    ctx = _create_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            data = json.loads(body)

            tier = str(data.get("tier", "free")).lower()
            char_count = int(data.get("character_count", 0))
            char_limit = int(data.get("character_limit", 10000))
            chars_left = max(0, char_limit - char_count)
            status = str(data.get("status", "active")).lower()

            is_exhausted = (char_limit > 0 and chars_left <= 0)
            status_desc = "quota_exhausted" if is_exhausted else "valid"
            tier_display = tier.capitalize()

            msg = (
                f"Valid ({tier_display} tier · {chars_left:,} / {char_limit:,} chars left)"
                if not is_exhausted else
                f"Quota Exceeded ({tier_display} tier · 0 chars left)"
            )

            return {
                "valid": True,
                "key": api_key,
                "masked": masked,
                "tier": tier,
                "character_count": char_count,
                "character_limit": char_limit,
                "characters_left": chars_left,
                "status": status_desc,
                "message": msg,
                "checked_at": now_iso
            }

    except urllib.error.HTTPError as e:
        code = e.code
        err_msg = ""
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            if isinstance(err_data, dict):
                detail = err_data.get("detail", {})
                if isinstance(detail, dict):
                    err_msg = detail.get("message", "")
                elif isinstance(detail, str):
                    err_msg = detail
        except Exception:
            pass

        if code == 401:
            friendly = f"Invalid API Key (HTTP 401: {err_msg or 'Unauthorized'})"
            status_val = "invalid"
        elif code == 429:
            friendly = f"Rate limited or quota exceeded (HTTP 429: {err_msg or 'Too Many Requests'})"
            status_val = "quota_exhausted"
        else:
            friendly = f"HTTP Error {code}: {err_msg or e.reason}"
            status_val = "error"

        return {
            "valid": False,
            "key": api_key,
            "masked": masked,
            "tier": "unknown",
            "character_count": 0,
            "character_limit": 0,
            "characters_left": 0,
            "status": status_val,
            "message": friendly,
            "checked_at": now_iso
        }

    except urllib.error.URLError as e:
        return {
            "valid": False,
            "key": api_key,
            "masked": masked,
            "tier": "unknown",
            "character_count": 0,
            "character_limit": 0,
            "characters_left": 0,
            "status": "network_error",
            "message": f"Connection error: {e.reason}",
            "checked_at": now_iso
        }
    except Exception as e:
        return {
            "valid": False,
            "key": api_key,
            "masked": masked,
            "tier": "unknown",
            "character_count": 0,
            "character_limit": 0,
            "characters_left": 0,
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "checked_at": now_iso
        }


def validate_bulk_keys(
    keys_input: Union[str, List[str]],
    max_workers: int = 4,
    timeout: float = 12.0,
    progress_cb: Optional[Callable[[int, int, dict], None]] = None
) -> List[dict]:
    """
    Validate multiple API keys in parallel.
    Calls progress_cb(completed_count, total_count, latest_result) if provided.
    """
    if isinstance(keys_input, str):
        keys = parse_bulk_keys(keys_input)
    else:
        keys = []
        seen = set()
        for k in keys_input:
            clean = (k or "").strip().strip('"\'`')
            if clean and clean not in seen:
                seen.add(clean)
                keys.append(clean)

    if not keys:
        return []

    results: List[dict] = [None] * len(keys)  # preserve key order
    key_to_idx = {k: i for i, k in enumerate(keys)}
    completed = 0
    total = len(keys)

    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(keys)))) as pool:
        future_map = {pool.submit(validate_api_key, k, timeout): k for k in keys}
        for future in as_completed(future_map):
            k = future_map[future]
            idx = key_to_idx[k]
            try:
                res = future.result()
            except Exception as e:
                res = {
                    "valid": False,
                    "key": k,
                    "masked": mask_key(k),
                    "tier": "unknown",
                    "character_count": 0,
                    "character_limit": 0,
                    "characters_left": 0,
                    "status": "error",
                    "message": str(e),
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            results[idx] = res
            completed += 1
            if progress_cb:
                try:
                    progress_cb(completed, total, res)
                except Exception:
                    pass

    return results


def fetch_elevenlabs_voices(api_key: Optional[str] = None, timeout: float = 12.0) -> Tuple[List[dict], Dict[str, dict]]:
    """
    Fetch all available voices for the given API key (or public voices if key is None).
    Calls GET https://api.elevenlabs.io/v1/voices

    Returns:
        (raw_voices_list, catalogue_dict)
    where catalogue_dict is ready to be merged into VOICE_CATALOGUE.
    """
    headers = {"User-Agent": "LocalTTS/3.1"}
    if api_key:
        headers["xi-api-key"] = api_key.strip()

    url = f"{ELEVENLABS_API_BASE}/voices"
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = _create_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            voices = data.get("voices", [])
    except urllib.error.HTTPError as e:
        err_msg = ""
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            err_msg = err_data.get("detail", {}).get("message", "")
        except Exception:
            pass
        raise RuntimeError(f"ElevenLabs API error ({e.code}): {err_msg or e.reason}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch voices from ElevenLabs: {e}")

    catalogue_entries: Dict[str, dict] = {}
    normalized_list: List[dict] = []

    for v in voices:
        v_id = v.get("voice_id", "").strip()
        v_name = v.get("name", "").strip()
        if not v_id or not v_name:
            continue

        category = v.get("category", "premade").lower()
        labels = v.get("labels", {}) or {}
        gender = str(labels.get("gender", "neutral")).lower()
        if gender not in ("female", "male"):
            gender = "neutral"

        accent = str(labels.get("accent", "")).strip()
        use_case = str(labels.get("use_case", "")).strip()
        raw_desc = str(v.get("description", "")).strip()

        # Build clean description
        desc_parts = []
        if category and category != "premade":
            desc_parts.append(f"[{category.capitalize()}]")
        if accent:
            desc_parts.append(accent.capitalize())
        if use_case:
            desc_parts.append(use_case.capitalize())
        if raw_desc:
            desc_parts.append(raw_desc)
        elif not desc_parts:
            desc_parts.append(f"ElevenLabs {category} voice")

        desc = " · ".join(desc_parts)

        # Build catalogue key: "Rachel  ·  ElevenLabs (Female)"
        g_badge = gender.capitalize()
        cat_key = f"{v_name}  ·  ElevenLabs ({g_badge})"

        # Handle collisions if same name exists
        if cat_key in catalogue_entries:
            cat_key = f"{v_name} [{v_id[:4]}]  ·  ElevenLabs ({g_badge})"

        entry = {
            "id": v_id,
            "name": v_name,
            "lang": "multilingual",
            "gender": gender,
            "backend": "elevenlabs",
            "desc": desc,
            "category": category,
            "accent": accent,
            "preview_url": v.get("preview_url", "")
        }

        catalogue_entries[cat_key] = entry
        normalized_list.append(entry)

    return normalized_list, catalogue_entries


class ElevenLabsKeyManager:
    """Manages stored ElevenLabs API keys, tracking active pool, failover, and quota."""

    @staticmethod
    def get_stored_keys(cfg: dict) -> List[dict]:
        """Return list of key dicts stored in config."""
        raw = cfg.get("elevenlabs_api_keys", [])
        clean: List[dict] = []
        for item in raw:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    clean.append({
                        "key": item,
                        "masked": mask_key(item),
                        "status": "valid",
                        "tier": "unknown",
                        "characters_left": -1,
                        "character_limit": -1,
                        "message": "Saved key",
                        "checked_at": ""
                    })
            elif isinstance(item, dict) and item.get("key"):
                clean.append(item)
        return clean

    @staticmethod
    def get_active_key(cfg: dict) -> Optional[str]:
        """Return the current working API key, or None if none configured."""
        keys = ElevenLabsKeyManager.get_stored_keys(cfg)
        for k in keys:
            if k.get("status") in ("valid", "active"):
                return k["key"]
        if keys:
            # Fallback to first key if status unknown
            return keys[0]["key"]
        return None

    @staticmethod
    def is_quota_or_auth_error(code: int, err_body: str) -> Tuple[bool, str]:
        """Determine if an HTTP error is due to auth failure or credit/quota exhaustion."""
        body_lower = (err_body or "").lower()
        if code in (401, 403):
            return True, "invalid"
        if code in (402, 429):
            return True, "quota_exhausted"
        if code >= 400:
            quota_keywords = [
                "quota", "credit", "character_limit", "characters remaining",
                "not enough", "exceeded", "payment_required", "insufficient",
                "too many requests", "rate_limit", "unauthorized", "invalid_api_key",
                "blocked"
            ]
            if any(k in body_lower for k in quota_keywords):
                return True, "quota_exhausted"
        return False, ""

    @staticmethod
    def rotate_exhausted_key(cfg: dict, exhausted_key: str, reason: str = "quota_exhausted") -> Optional[str]:
        """
        Mark a key as exhausted/invalid and return the next valid key in the pool.
        Saves updated status back to cfg.
        """
        keys = ElevenLabsKeyManager.get_stored_keys(cfg)
        next_key = None
        for k in keys:
            if k["key"] == exhausted_key:
                k["status"] = reason
                k["characters_left"] = 0
                k["message"] = f"Credits finished ({reason}) at {datetime.now().strftime('%H:%M:%S')}"
            elif not next_key and k.get("status") in ("valid", "active"):
                next_key = k["key"]

        cfg["elevenlabs_api_keys"] = keys
        from config.settings import save
        save(cfg)
        log.warn(f"ElevenLabs Key {mask_key(exhausted_key)} marked as {reason}. Next active key: {mask_key(next_key) if next_key else 'None'}")
        return next_key


def synthesize_elevenlabs_audio(
    text: str,
    voice_id: str,
    out_wav_path: str,
    api_key: Optional[str] = None,
    model_id: str = DEFAULT_MODEL_ID,
    speed: float = 1.0,
    cb: Optional[Callable[[str], None]] = None
) -> float:
    """
    Synthesize text using ElevenLabs API and write directly to out_wav_path (PCM_16 WAV).
    Supports automatic key rotation if active key hits quota exhaustion.

    Returns the measured audio duration in seconds.
    """
    import soundfile as sf
    from config.settings import load as load_settings

    cfg = load_settings()

    # Determine key to use
    if not api_key:
        api_key = ElevenLabsKeyManager.get_active_key(cfg)

    stored_keys = ElevenLabsKeyManager.get_stored_keys(cfg)
    valid_stored = [k["key"] for k in stored_keys if k.get("status") in ("valid", "active")]

    if api_key and api_key in valid_stored:
        candidate_keys = [api_key] + [k for k in valid_stored if k != api_key]
    elif valid_stored:
        candidate_keys = valid_stored
    elif api_key:
        candidate_keys = [api_key]
    else:
        raise RuntimeError(
            "No valid ElevenLabs API key found! Please go to Settings → ElevenLabs and add an API key."
        )

    last_err = None

    for attempt, cur_key in enumerate(candidate_keys, 1):
        if cb:
            cb(f"Synthesizing with ElevenLabs (key {attempt}/{len(candidate_keys)})…")

        url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}?output_format=mp3_44100_128"
        headers = {
            "xi-api-key": cur_key.strip(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "User-Agent": "LocalTTS/3.1"
        }

        # Build payload
        voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
        # ElevenLabs supports speed parameter 0.7 to 1.2
        if speed != 1.0 and 0.7 <= speed <= 1.2:
            voice_settings["speed"] = round(float(speed), 2)

        payload = {
            "text": text,
            "model_id": model_id or DEFAULT_MODEL_ID,
            "voice_settings": voice_settings
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        ctx = _create_ssl_context()

        tmp_mp3 = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_mp3 = tf.name

            with urllib.request.urlopen(req, timeout=60.0, context=ctx) as resp:
                with open(tmp_mp3, "wb") as f_out:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f_out.write(chunk)

            # Validate audio received
            if not os.path.exists(tmp_mp3) or os.path.getsize(tmp_mp3) == 0:
                raise RuntimeError("Empty audio stream received from ElevenLabs.")

            # Read decoded MP3
            audio_samples, sample_rate = sf.read(tmp_mp3)

            # Convert stereo to mono if needed
            if audio_samples.ndim > 1:
                audio_samples = audio_samples.mean(axis=1)

            # Master audio if enabled
            if cfg.get("enhance_audio", True):
                from core.tts_backend import master_audio
                audio_samples = master_audio(audio_samples, sample_rate)

            # Ensure parent output directory exists
            Path(out_wav_path).parent.mkdir(parents=True, exist_ok=True)

            # Write standard PCM_16 WAV
            sf.write(out_wav_path, audio_samples, sample_rate, subtype="PCM_16")

            duration = len(audio_samples) / float(sample_rate)
            log.info(f"ElevenLabs synthesis successful on key {mask_key(cur_key)}: {duration:.2f}s audio written to {out_wav_path}")
            return duration

        except urllib.error.HTTPError as e:
            code = e.code
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass

            log.warn(f"ElevenLabs HTTP {code} on key {mask_key(cur_key)}: {err_body}")

            is_quota, reason = ElevenLabsKeyManager.is_quota_or_auth_error(code, err_body)
            if is_quota:
                next_key = ElevenLabsKeyManager.rotate_exhausted_key(cfg, cur_key, reason)
                if cb:
                    next_str = mask_key(next_key) if next_key else "none"
                    cb(f"API key {mask_key(cur_key)} credits finished. Switched to next key ({next_str})…")
                last_err = RuntimeError(f"ElevenLabs key {mask_key(cur_key)} credits finished ({reason}, HTTP {code}).")
                # Continue retry loop with next candidate key
                continue
            else:
                raise RuntimeError(f"ElevenLabs synthesis failed (HTTP {code}): {err_body or e.reason}")

        except Exception as e:
            last_err = e
            log.error(f"ElevenLabs synthesis error on key {mask_key(cur_key)}: {e}")
            break

        finally:
            if tmp_mp3 and os.path.exists(tmp_mp3):
                try:
                    os.remove(tmp_mp3)
                except OSError:
                    pass

    # If all keys failed
    raise RuntimeError(
        f"All available ElevenLabs API keys failed or ran out of credits. Last error: {last_err}"
    )
