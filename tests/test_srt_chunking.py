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

def test_srt_with_timed_segments(tmp_path):
    if isinstance(generate_srt, unittest.mock.MagicMock):
        if 'core.tts_backend' in sys.modules:
            del sys.modules['core.tts_backend']
        import core.tts_backend
        real_gen = core.tts_backend.generate_srt
    else:
        real_gen = generate_srt

    out_audio = tmp_path / "audio.wav"
    timed_segments = [
        {"text": "First chunk from audio buffer.", "start": 0.0, "end": 2.35},
        {"text": "Second chunk accurately measured.", "start": 2.35, "end": 4.90},
        {"text": "Third very long chunk that should be split into smaller blocks.", "start": 4.90, "end": 9.50},
    ]
    real_gen("Full text", 9.50, str(out_audio), timed_segments=timed_segments)

    srt_file = tmp_path / "transcript.srt"
    assert srt_file.exists()
    entries = parse_srt_file(srt_file)
    assert len(entries) >= 3
    # Check that timestamps start at 0.0 and end around 9.50 and no chunk > 3.0s
    assert abs(entries[0][1] - 0.0) < 0.01
    assert abs(entries[-1][2] - 9.50) < 0.05
    for idx, s, e, txt in entries:
        dur = e - s
        assert dur <= 3.001, f"Chunk {idx} ({txt}) duration {dur} > 3.0s"


def test_preprocess_text_for_pacing_and_compounds():
    from core.tts_backend import preprocess_text_for_pacing, chunk_text, calculate_chunk_pause

    # Test 1: "world wide web" is unified into a cohesive compound so it is spoken in one breath
    text1 = "decades before the world wide web was ever born"
    res1 = preprocess_text_for_pacing(text1)
    assert "world-wide-web" in res1

    # Test 1b: Typo variant "word wide web" and "worldwide web" are also unified
    text1b = "decades before the word wide web was ever born"
    res1b = preprocess_text_for_pacing(text1b)
    assert "world-wide-web" in res1b

    text1c = "an active terminal in a worldwide web of living humans"
    res1c = preprocess_text_for_pacing(text1c)
    assert "world-wide-web" in res1c

    # Test 2: Double dash "--" is converted to em-dash " — " with breathing space
    text2 = "word wide -- web which sounds weired"
    res2 = preprocess_text_for_pacing(text2)
    assert " — " in res2

    # Test 3: Spaced hyphen "break -in" or "word -wide" is reconnected
    text3 = "This was a midnight break -in and a world -wide event."
    res3 = preprocess_text_for_pacing(text3)
    assert "break-in" in res3
    assert "world-wide" in res3

    # Test 4: Natural ellipses formatting
    text4 = "Wait...what happened?"
    res4 = preprocess_text_for_pacing(text4)
    assert "Wait... what happened?" in res4

    # Test 5: Clause, sentence, and paragraph pause calculations
    assert calculate_chunk_pause("Sentence.\n") == 0.65  # Paragraph pause
    assert calculate_chunk_pause("Sentence.") == 0.38    # Sentence breath pause
    assert calculate_chunk_pause("Sentence...") == 0.48  # Dramatic / reflective ellipsis pause
    assert calculate_chunk_pause("Sentence —") == 0.24   # Em-dash suspension pause
    assert calculate_chunk_pause("Sentence,") == 0.15    # Clause breath pause
    assert calculate_chunk_pause("Sentence") == 0.06     # Micro-gap for split sub-clauses

    # Test 6: Long sentence clause-based splitting does not break compound phrases
    long_sent = (
        "Decades before modern technology transformed our daily lives and created computers that fit in our pockets, "
        "researchers were experimenting with strange new communication methods in secret laboratories across the nation; "
        "and theorists believed that these networks would eventually evolve into the world wide web which connects billions of devices."
    )
    chunks = chunk_text(long_sent, limit=250)
    assert len(chunks) >= 2
    # Check that 'world-wide-web' is kept together inside one chunk
    www_chunks = [c for c in chunks if "world-wide-web" in c]
    assert len(www_chunks) == 1
    assert "world-wide-web" in www_chunks[0]

    # Test 7: Paragraph break preservation across multi-paragraph scripts
    multi_para = (
        "This is paragraph one.\n\n"
        "This is paragraph two."
    )
    p_chunks = chunk_text(multi_para, limit=300)
    assert len(p_chunks) == 2
    assert p_chunks[0].endswith("\n")
    assert calculate_chunk_pause(p_chunks[0]) == 0.65


