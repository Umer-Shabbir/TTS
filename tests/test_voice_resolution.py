import pytest
import json
from pathlib import Path
from config.settings import resolve_voice, extract_voice_from_meta, VOICE_CATALOGUE, DEFAULT_VOICE
from core.file_handler import scan_master_folder


def test_resolve_voice_exact_match():
    assert resolve_voice("Adam   ·  American Male") == "Adam   ·  American Male"
    assert resolve_voice("Heart  ·  American Female") == "Heart  ·  American Female"


def test_resolve_voice_by_voice_id():
    assert resolve_voice("am_adam") == "Adam   ·  American Male"
    assert resolve_voice("af_heart") == "Heart  ·  American Female"
    assert resolve_voice("af_bella") == "Bella  ·  American Female"
    assert resolve_voice("bm_george") == "George ·  British Male"
    assert resolve_voice("pt_BR-faber-medium") == "Faber  ·  Portuguese Male (Offline)"
    assert resolve_voice("ur_PK-aegis_female-medium") == "Aegis  ·  Urdu Female (Offline)"
    assert resolve_voice("ko-KR-InJoonNeural") == "InJoon ·  Korean Male (Online)"


def test_resolve_voice_by_short_name():
    assert resolve_voice("Adam") == "Adam   ·  American Male"
    assert resolve_voice("Heart") == "Heart  ·  American Female"
    assert resolve_voice("Bella") == "Bella  ·  American Female"
    assert resolve_voice("George") == "George ·  British Male"


def test_resolve_voice_by_normalized_spacing():
    assert resolve_voice("Adam · American Male") == "Adam   ·  American Male"
    assert resolve_voice("heart · american female") == "Heart  ·  American Female"


def test_resolve_voice_alias():
    assert resolve_voice("en_us_male_dry_narrator") == "Adam   ·  American Male"
    assert resolve_voice("en_us_female_narrator") == "Heart  ·  American Female"


def test_resolve_voice_fallback():
    assert resolve_voice("unknown_voice_xyz") == DEFAULT_VOICE
    assert resolve_voice("") == DEFAULT_VOICE
    assert resolve_voice(None) == DEFAULT_VOICE


def test_extract_voice_from_meta_fields():
    assert extract_voice_from_meta({"voice_id": "af_bella"}) == "Bella  ·  American Female"
    assert extract_voice_from_meta({"voice_name": "am_adam"}) == "Adam   ·  American Male"
    assert extract_voice_from_meta({"voice": "George"}) == "George ·  British Male"
    assert extract_voice_from_meta({"tts_voice": "Heart"}) == "Heart  ·  American Female"
    assert extract_voice_from_meta({"preset_name": "paper_glass"}) == "Adam   ·  American Male"


def test_scan_master_folder_script_ready_stage(tmp_path):
    master_dir = tmp_path / "master"
    master_dir.mkdir()

    # Create project folder with stage SCRIPT_READY and voice_id am_adam
    proj = master_dir / "test_project"
    proj.mkdir()
    (proj / "script.txt").write_text("Test narration script.")
    (proj / "project.json").write_text(json.dumps({
        "stage": "SCRIPT_READY",
        "status": "PENDING",
        "voice_id": "af_bella"
    }))

    folders = scan_master_folder(str(master_dir))
    assert len(folders) == 1
    assert folders[0] == proj
