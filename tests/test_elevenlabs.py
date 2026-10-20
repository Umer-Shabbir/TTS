"""
tests/test_elevenlabs.py – Unit tests for ElevenLabs API client, bulk keys,
validation, voice catalog caching, and backend synthesis routing.
"""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from core.elevenlabs_client import (
    ElevenLabsKeyManager,
    fetch_elevenlabs_voices,
    mask_key,
    parse_bulk_keys,
    synthesize_elevenlabs_audio,
    validate_api_key,
    validate_bulk_keys,
)
from config.settings import VOICE_CATALOGUE, resolve_voice, sync_elevenlabs_voices


class TestBulkKeysParsing:
    def test_parse_single_key(self):
        res = parse_bulk_keys("sk_test123456789")
        assert res == ["sk_test123456789"]

    def test_parse_multiline_and_delimiters(self):
        text = """
        sk_key1, sk_key2; sk_key3
        sk_key4
        sk_key5 sk_key6
        """
        res = parse_bulk_keys(text)
        assert res == ["sk_key1", "sk_key2", "sk_key3", "sk_key4", "sk_key5", "sk_key6"]

    def test_parse_ignores_comments_and_quotes(self):
        text = """
        # Primary keys:
        "sk_quoted_1"
        'sk_quoted_2'
        // Secondary key:
        sk_unquoted_3
        # Empty lines below:

        """
        res = parse_bulk_keys(text)
        assert res == ["sk_quoted_1", "sk_quoted_2", "sk_unquoted_3"]

    def test_parse_deduplicates_preserving_order(self):
        text = "keyA, keyB, keyA, keyC, keyB"
        res = parse_bulk_keys(text)
        assert res == ["keyA", "keyB", "keyC"]

    def test_mask_key(self):
        assert mask_key("") == ""
        assert mask_key("short") == "***"
        assert mask_key("sk_1234567890abcdef") == "sk_123...cdef"


class TestValidation:
    @patch("urllib.request.urlopen")
    def test_validate_valid_key(self, mock_urlopen):
        # Mock 200 response with subscription data
        resp_data = {
            "tier": "starter",
            "character_count": 5000,
            "character_limit": 30000,
            "status": "active"
        }
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps(resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = validate_api_key("sk_valid_key_12345")
        assert res["valid"] is True
        assert res["tier"] == "starter"
        assert res["character_count"] == 5000
        assert res["character_limit"] == 30000
        assert res["characters_left"] == 25000
        assert res["status"] == "valid"
        assert "Valid (Starter" in res["message"]

    @patch("urllib.request.urlopen")
    def test_validate_exhausted_key(self, mock_urlopen):
        resp_data = {
            "tier": "free",
            "character_count": 10000,
            "character_limit": 10000,
            "status": "active"
        }
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps(resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = validate_api_key("sk_exhausted_key")
        assert res["valid"] is True
        assert res["status"] == "quota_exhausted"
        assert res["characters_left"] == 0
        assert "Quota Exceeded" in res["message"]

    @patch("urllib.request.urlopen")
    def test_validate_invalid_key_401(self, mock_urlopen):
        err_body = json.dumps({
            "detail": {"status": "invalid_api_key", "message": "Invalid API key"}
        }).encode("utf-8")
        http_err = urllib.error.HTTPError(
            url="https://api.elevenlabs.io/v1/user/subscription",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(err_body)
        )
        mock_urlopen.side_effect = http_err

        res = validate_api_key("sk_invalid_key")
        assert res["valid"] is False
        assert res["status"] == "invalid"
        assert "Invalid API Key" in res["message"]

    @patch("urllib.request.urlopen")
    def test_validate_rate_limited_429(self, mock_urlopen):
        err_body = json.dumps({
            "detail": {"message": "Too Many Requests"}
        }).encode("utf-8")
        http_err = urllib.error.HTTPError(
            url="https://api.elevenlabs.io/v1/user/subscription",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(err_body)
        )
        mock_urlopen.side_effect = http_err

        res = validate_api_key("sk_rate_limited")
        assert res["valid"] is False
        assert res["status"] == "quota_exhausted"
        assert "429" in res["message"]

    @patch("core.elevenlabs_client.validate_api_key")
    def test_validate_bulk_keys(self, mock_validate):
        mock_validate.side_effect = lambda k, *a, **kw: {
            "key": k,
            "valid": "valid" in k,
            "masked": mask_key(k),
            "tier": "free",
            "characters_left": 1000 if "valid" in k else 0,
            "character_limit": 1000,
            "character_count": 0,
            "status": "valid" if "valid" in k else "invalid",
            "message": "ok" if "valid" in k else "fail"
        }

        results = validate_bulk_keys(["sk_valid_1", "sk_bad_2", "sk_valid_3"])
        assert len(results) == 3
        assert results[0]["valid"] is True
        assert results[1]["valid"] is False
        assert results[2]["valid"] is True


class TestKeyManager:
    def test_get_stored_keys_and_active_key(self):
        cfg = {
            "elevenlabs_api_keys": [
                {"key": "sk_key1", "status": "quota_exhausted"},
                {"key": "sk_key2", "status": "valid"},
                "sk_key3_as_string"
            ]
        }
        stored = ElevenLabsKeyManager.get_stored_keys(cfg)
        assert len(stored) == 3
        assert stored[0]["key"] == "sk_key1"
        assert stored[2]["key"] == "sk_key3_as_string"

        active = ElevenLabsKeyManager.get_active_key(cfg)
        assert active == "sk_key2"

    @patch("config.settings.save")
    def test_rotate_exhausted_key(self, mock_save):
        cfg = {
            "elevenlabs_api_keys": [
                {"key": "sk_key1", "status": "valid"},
                {"key": "sk_key2", "status": "valid"}
            ]
        }
        next_key = ElevenLabsKeyManager.rotate_exhausted_key(cfg, "sk_key1", "quota_exhausted")
        assert next_key == "sk_key2"
        assert cfg["elevenlabs_api_keys"][0]["status"] == "quota_exhausted"


class TestVoicesAndCatalogue:
    @patch("urllib.request.urlopen")
    def test_fetch_voices(self, mock_urlopen):
        voices_payload = {
            "voices": [
                {
                    "voice_id": "vid_rachel_123",
                    "name": "Rachel",
                    "category": "premade",
                    "labels": {"gender": "female", "accent": "american", "use_case": "narration"},
                    "description": "Calm voice",
                    "preview_url": "https://preview.mp3"
                },
                {
                    "voice_id": "vid_custom_456",
                    "name": "Custom Voice",
                    "category": "cloned",
                    "labels": {"gender": "male", "accent": "british"},
                    "description": "",
                    "preview_url": ""
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(voices_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        raw_list, cat_dict = fetch_elevenlabs_voices("sk_dummy")
        assert len(raw_list) == 2
        assert len(cat_dict) == 2

        assert "Rachel  ·  ElevenLabs (Female)" in cat_dict
        rachel_entry = cat_dict["Rachel  ·  ElevenLabs (Female)"]
        assert rachel_entry["id"] == "vid_rachel_123"
        assert rachel_entry["backend"] == "elevenlabs"
        assert rachel_entry["gender"] == "female"

        assert "Custom Voice  ·  ElevenLabs (Male)" in cat_dict

    def test_catalogue_sync_and_resolution(self):
        sample_voices = {
            "SpecialCloned  ·  ElevenLabs (Female)": {
                "id": "cloned_abc_123",
                "name": "SpecialCloned",
                "gender": "female",
                "backend": "elevenlabs",
                "desc": "Cloned Voice"
            }
        }
        sync_elevenlabs_voices(sample_voices)

        assert "SpecialCloned  ·  ElevenLabs (Female)" in VOICE_CATALOGUE

        # Test resolution by ID
        resolved_by_id = resolve_voice("cloned_abc_123")
        assert resolved_by_id == "SpecialCloned  ·  ElevenLabs (Female)"

        # Test resolution by name
        resolved_by_name = resolve_voice("SpecialCloned")
        assert resolved_by_name == "SpecialCloned  ·  ElevenLabs (Female)"


class TestBackendRouting:
    def test_resolve_default_elevenlabs_premade_voices(self):
        # Default catalogue includes Rachel, Adam, Antoni, etc.
        assert "Rachel ·  ElevenLabs (Female)" in VOICE_CATALOGUE or "Rachel  ·  ElevenLabs (Female)" in VOICE_CATALOGUE
        res_rachel = resolve_voice("21m00Tcm4TlvDq8ikWAM")
        assert "ElevenLabs" in res_rachel
        cfg = VOICE_CATALOGUE[res_rachel]
        assert cfg["backend"] == "elevenlabs"
        assert cfg["id"] == "21m00Tcm4TlvDq8ikWAM"


class TestPresetVoiceAssignments:
    def test_all_presets_have_unique_offline_and_elevenlabs_voices(self):
        from pathlib import Path
        reg_file = Path("H:/Automation/Presets/master_presets_registry.json")
        assert reg_file.exists(), "master_presets_registry.json must exist"

        data = json.loads(reg_file.read_text(encoding="utf-8"))
        assert len(data) == 17, "There should be 17 presets"

        offline_voices = set()
        elevenlabs_voices = set()

        for name, p_info in data.items():
            off_v = p_info.get("offline_voice")
            el_v = p_info.get("elevenlabs_voice")

            assert off_v, f"Preset '{name}' missing offline_voice"
            assert el_v, f"Preset '{name}' missing elevenlabs_voice"

            # Check that each offline voice is only assigned once
            assert off_v not in offline_voices, f"Offline voice '{off_v}' duplicated in preset '{name}'"
            offline_voices.add(off_v)

            # Check that each ElevenLabs voice is only assigned once
            assert el_v not in elevenlabs_voices, f"ElevenLabs voice '{el_v}' duplicated in preset '{name}'"
            elevenlabs_voices.add(el_v)

            # Verify that voices dictionary is properly present
            assert "voices" in p_info
            assert p_info["voices"]["offline"] == off_v
            assert p_info["voices"]["elevenlabs"] == el_v

        assert len(offline_voices) == 17
        assert len(elevenlabs_voices) == 17

    def test_extract_voice_from_meta_preset(self):
        from config.settings import extract_voice_from_meta

        # Default resolution picks offline voice
        res_default = extract_voice_from_meta({"preset_name": "blueprint"})
        assert "Adam" in res_default

        # ElevenLabs mode picks elevenlabs_voice
        res_el = extract_voice_from_meta({"preset_name": "blueprint", "use_elevenlabs": True})
        assert "Jonathan" in res_el

        # Another preset
        res_yoga_off = extract_voice_from_meta({"preset_name": "rainbow_yoga"})
        assert "Nicole" in res_yoga_off

        res_yoga_el = extract_voice_from_meta({"preset_name": "rainbow_yoga", "voice_backend": "elevenlabs"})
        assert "Elli" in res_yoga_el


class TestMultiKeyChunkStitching:
    @patch("urllib.request.urlopen")
    def test_synth_stitches_chunks_across_multiple_keys(self, mock_urlopen):
        import sys
        import tempfile
        import os
        from unittest.mock import MagicMock
        from core.tts_backend import TTSEngine
        from config.settings import save, load
        orig_cfg = load()

        # Mock soundfile module so test runs cleanly without C-extension dependencies
        mock_sf = MagicMock()
        dummy_audio = MagicMock()
        dummy_audio.ndim = 1
        dummy_audio.__len__.return_value = 24000
        mock_sf.read.return_value = (dummy_audio, 24000)

        def fake_sf_write(path, samples, sr, subtype="PCM_16"):
            import wave
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(b"\x00\x00" * int(sr * 0.5))
        mock_sf.write.side_effect = fake_sf_write
        sys.modules["soundfile"] = mock_sf

        # Setup 2 keys in config
        test_cfg = {
            **orig_cfg,
            "elevenlabs_api_keys": [
                {"key": "sk_key_1", "status": "valid", "tier": "free", "characters_left": 100},
                {"key": "sk_key_2", "status": "valid", "tier": "starter", "characters_left": 5000}
            ],
            "enhance_audio": False,
            "smart_pacing": True,
            "elevenlabs_model_id": "eleven_multilingual_v2"
        }
        save(test_cfg)

        call_count = 0
        def fake_urlopen(req, timeout=None, context=None):
            nonlocal call_count
            call_count += 1
            key = req.headers.get("Xi-api-key")
            # First key succeeds on chunk 1, but runs out of credits on chunk 2!
            if key == "sk_key_1" and call_count > 1:
                err_body = json.dumps({"detail": {"status": "quota_exceeded", "message": "You have run out of credits."}}).encode("utf-8")
                raise urllib.error.HTTPError(
                    url=req.full_url,
                    code=429,
                    msg="Too Many Requests",
                    hdrs={},
                    fp=io.BytesIO(err_body)
                )

            # Succeeded call: returns dummy audio bytes
            m = MagicMock()
            m.read.side_effect = [b"RIFF\x24\x00\x00\x00WAVEfmt ", b""]
            m.__enter__.return_value = m
            return m

        mock_urlopen.side_effect = fake_urlopen

        # Text with 2 distinct sentences that form 2 chunks
        text = "This is chunk number one. This is chunk number two which will switch to key two."
        backend = TTSEngine()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            out_wav = tf.name

        try:
            cfg = {"id": "21m00Tcm4TlvDq8ikWAM", "backend": "elevenlabs", "name": "Rachel"}
            progress_messages = []
            segments = backend._synth_elevenlabs(
                text=text,
                out_path=out_wav,
                cfg=cfg,
                speed=1.0,
                chunk_limit=60,
                cb=lambda msg: progress_messages.append(msg)
            )

            # Both chunks should have been synthesized
            assert len(segments) >= 2
            # Stitched output file should have been written
            assert os.path.exists(out_wav)
            # Progress messages should capture key failover
            assert any("credits finished" in m or "Switched" in m for m in progress_messages)
        finally:
            save(orig_cfg)
            if os.path.exists(out_wav):
                try: os.remove(out_wav)
                except OSError: pass

