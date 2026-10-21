"""
Unit tests for TTS queue generation mode selection and UI integration.
Tests cover:
- QueueModeDialog (Local vs ElevenLabs mode confirmation / cancellation)
- SynthesizePage generation mode toggle and voice dropdown filtering
- Automatic mode switching on set_voice()
- JobCard Local vs ElevenLabs indicator icons
- Project folder preset voice extraction respecting mode
"""
import pytest
import tkinter as tk
from pathlib import Path
import json

from config.settings import VOICE_CATALOGUE, extract_voice_from_meta
from core.queue_manager import QueueManager, TTSJob
from ui.app import QueueModeDialog, SynthesizePage, JobCard


@pytest.fixture(scope="module")
def tk_root():
    """Create a headless Tk instance for UI testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_queue_mode_dialog_confirm(tk_root):
    """Test that QueueModeDialog allows selecting ElevenLabs and returns the selection."""
    def select_and_confirm():
        for child in tk_root.winfo_children():
            if isinstance(child, QueueModeDialog):
                child._select_mode("elevenlabs")
                child._on_confirm()
                return
        tk_root.after(10, select_and_confirm)

    tk_root.after(20, select_and_confirm)
    dlg = QueueModeDialog(tk_root, default_mode="local", count=3)
    assert dlg.result == "elevenlabs"


def test_queue_mode_dialog_cancel(tk_root):
    """Test that cancelling QueueModeDialog yields None."""
    def cancel():
        for child in tk_root.winfo_children():
            if isinstance(child, QueueModeDialog):
                child.destroy()
                return
        tk_root.after(10, cancel)

    tk_root.after(20, cancel)
    dlg = QueueModeDialog(tk_root, default_mode="local", count=1)
    assert dlg.result is None


def test_synthesize_page_mode_switching_and_filtering(tk_root):
    """Test that toggling generation mode filters voices and updates button labels."""
    cfg = {"generation_mode": "local", "voice": "Heart  ·  American Female", "speed": 1.0}
    qm = QueueManager(schedule_fn=tk_root.after)
    page = SynthesizePage(tk_root, cfg, qm, on_status=lambda _: None, on_navigate=lambda _: None)

    # 1. Local mode defaults
    assert page._generation_mode == "local"
    assert "[Local]" in page._btn_add.cget("text")
    local_voices = [k for k, v in VOICE_CATALOGUE.items() if v.get("backend") != "elevenlabs"]
    assert list(page._voice_cb["values"]) == local_voices

    # 2. Switch to ElevenLabs mode
    page._set_generation_mode("elevenlabs")
    assert page._generation_mode == "elevenlabs"
    assert "[ElevenLabs]" in page._btn_add.cget("text")
    el_voices = [k for k, v in VOICE_CATALOGUE.items() if v.get("backend") == "elevenlabs"]
    assert list(page._voice_cb["values"]) == el_voices

    # 3. set_voice with a local voice switches mode back to local
    page.set_voice("Heart  ·  American Female")
    assert page._generation_mode == "local"
    assert "[Local]" in page._btn_add.cget("text")

    # 4. set_voice with an ElevenLabs voice switches mode to elevenlabs
    page.set_voice(el_voices[0])
    assert page._generation_mode == "elevenlabs"
    assert "[ElevenLabs]" in page._btn_add.cget("text")


def test_job_card_mode_indicators(tk_root):
    """Test that JobCard renders the correct mode indicator icon."""
    # Local job
    local_voice = "Heart  ·  American Female"
    j_local = TTSJob(text="Test local", voice=local_voice, output_path="out1.wav")
    card_local = JobCard(tk_root, j_local, on_retry=lambda: None, on_cancel=lambda: None)
    
    local_labels = []
    for child in card_local.winfo_children():
        if isinstance(child, tk.Frame):
            local_labels.extend([w.cget("text") for w in child.winfo_children() if isinstance(w, tk.Label)])
    assert any("💻 Local" in t for t in local_labels)

    # ElevenLabs job
    el_voice = [k for k, v in VOICE_CATALOGUE.items() if v.get("backend") == "elevenlabs"][0]
    j_el = TTSJob(text="Test EL", voice=el_voice, output_path="out2.wav")
    card_el = JobCard(tk_root, j_el, on_retry=lambda: None, on_cancel=lambda: None)
    
    el_labels = []
    for child in card_el.winfo_children():
        if isinstance(child, tk.Frame):
            el_labels.extend([w.cget("text") for w in child.winfo_children() if isinstance(w, tk.Label)])
    assert any("☁️ EL" in t for t in el_labels)


def test_preset_voice_resolution_respects_generation_mode():
    """Verify that presets resolve differently based on explicit mode."""
    meta = {"preset_name": "blueprint"}
    
    voice_local = extract_voice_from_meta(meta, mode="local")
    voice_el = extract_voice_from_meta(meta, mode="elevenlabs")

    assert voice_local != voice_el
    assert VOICE_CATALOGUE[voice_local]["backend"] != "elevenlabs"
    assert VOICE_CATALOGUE[voice_el]["backend"] == "elevenlabs"
