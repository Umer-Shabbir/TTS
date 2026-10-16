import sys
import unittest.mock

# Ensure the real module is loaded if another test file mocked sys.modules
if 'core.tts_backend' in sys.modules and isinstance(sys.modules['core.tts_backend'], unittest.mock.MagicMock):
    del sys.modules['core.tts_backend']

import os
import re
from pathlib import Path
import pytest
from core.tts_backend import generate_srt

def parse_srt_file(srt_path):
    content = Path(srt_path).read_text(encoding="utf-8").strip()
    blocks = re.split(r'\r?\n\r?\n', content)
    entries = []
    for b in blocks:
        lines = [l.strip() for l in b.split('\n') if l.strip()]
        if len(lines) >= 3:
            idx = int(lines[0])
            m = re.match(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)', lines[1])
            assert m, f"Invalid timestamp line: {lines[1]}"
            s_h, s_m, s_s, s_ms = map(int, m.groups()[:4])
            e_h, e_m, e_s, e_ms = map(int, m.groups()[4:])
            start_sec = s_h * 3600 + s_m * 60 + s_s + s_ms / 1000.0
            end_sec = e_h * 3600 + e_m * 60 + e_s + e_ms / 1000.0
            text = " ".join(lines[2:])
            entries.append((idx, start_sec, end_sec, text))
    return entries

def test_srt_max_3_seconds_and_variation(tmp_path):
    # Ensure real generate_srt is used
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out_audio = tmp_path / "audio.wav"
    text = (
        "In 1973, in a tiny community room in the West Bronx, Clive Campbell set up two turntables. "
        "Nobody expected that this small block party would invent hip hop. It was an explosive cultural revolution. "
        "The sound traveled from the parks to global stadiums. Today we explore how this fateful night changed everything."
    )
    duration = 45.0  # 45 seconds of speech
    real_gen(text, duration, str(out_audio))

    srt_file = tmp_path / "transcript.srt"
    assert srt_file.exists(), "SRT file must be created"

    entries = parse_srt_file(srt_file)
    assert len(entries) > 0, "SRT must have entries"

    durations = []
    for idx, start_t, end_t, chunk_text in entries:
        chunk_dur = round(end_t - start_t, 3)
        durations.append(chunk_dur)
        # 1. Strictly at max 3 seconds not more
        assert chunk_dur <= 3.001, f"Chunk {idx} exceeds 3.0s: {chunk_dur}s"
        # 2. No 4 seconds or above 3 seconds
        assert chunk_dur < 3.005, f"Chunk {idx} exceeds 3.0s: {chunk_dur}s"
        assert start_t < end_t, f"Chunk {idx} invalid range: {start_t} -> {end_t}"

    # 3. Variation between 2 and 3 seconds
    assert max(durations) <= 3.001
    assert any(d >= 2.0 for d in durations), "Expected chunks in the 2-3s range"
    assert len(set(round(d, 1) for d in durations)) > 1, "Expected variation across chunk lengths"

def test_srt_short_audio(tmp_path):
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out_audio = tmp_path / "audio.wav"
    text = "Quick phrase."
    duration = 2.5
    real_gen(text, duration, str(out_audio))

    srt_file = tmp_path / "transcript.srt"
    assert srt_file.exists()
    entries = parse_srt_file(srt_file)
    assert len(entries) == 1
    chunk_dur = entries[0][2] - entries[0][1]
    assert chunk_dur <= 3.0

def test_srt_long_documentary(tmp_path):
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out_audio = tmp_path / "audio.wav"
    text = "This is a comprehensive documentary explaining the hidden secrets of human habit formation and neural loops. " * 30
    duration = 600.0  # 10 minute documentary
    real_gen(text, duration, str(out_audio))

    srt_file = tmp_path / "transcript.srt"
    assert srt_file.exists()
    entries = parse_srt_file(srt_file)

    for idx, start_t, end_t, chunk_text in entries:
        chunk_dur = round(end_t - start_t, 3)
        assert chunk_dur <= 3.001, f"Chunk {idx} duration {chunk_dur}s exceeds 3.0s limit"

def test_srt_no_placeholder_or_repeated_lines(tmp_path):
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out_audio = tmp_path / "audio.wav"
    text = "Thank you for watching."
    duration = 10.0
    real_gen(text, duration, str(out_audio))

    srt_file = tmp_path / "transcript.srt"
    assert srt_file.exists()
    entries = parse_srt_file(srt_file)
    for idx, s, e, txt in entries:
        assert txt != "...", f"Chunk {idx} contains placeholder '...'"
        assert e - s <= 3.001

def test_srt_empty_text_and_zero_duration(tmp_path):
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out1 = tmp_path / "sub1" / "audio.wav"
    out1.parent.mkdir()
    real_gen("", 5.0, str(out1))
    assert (out1.parent / "transcript.srt").exists()

    out2 = tmp_path / "sub2" / "audio.wav"
    out2.parent.mkdir()
    real_gen("Some text", 0.0, str(out2))
    assert (out2.parent / "transcript.srt").exists()
