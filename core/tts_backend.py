"""
core/tts_backend.py – Multi-Backend TTS Engine (Kokoro, Piper, Edge-TTS)
Supports English (Kokoro), Multilingual Offline (Piper), and Online (Edge-TTS).
"""

import os
import wave
import asyncio
import tempfile
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import soundfile as sf

from config.settings import (
    VOICE_CATALOGUE, MODEL_FILE, VOICES_FILE, SAMPLE_RATE, CHUNK_CHAR_LIMIT, resolve_voice
)
from core.logger import log
from core.model_manager import ensure_piper_voice_downloaded


def split_segment_if_needed(text: str, start_t: float, end_t: float, max_duration: float = 3.0) -> List[dict]:
    """
    Ensure an audio segment does not exceed max_duration (3.0s).
    If it does, split on natural clause/word boundaries and distribute
    the TRUE measured audio duration proportionally based on character length.
    """
    dur = max(0.05, end_t - start_t)
    text = text.strip()
    if not text:
        return []
    if dur <= max_duration:
        return [{"text": text, "start": start_t, "end": end_t}]

    import math
    import re
    k = max(2, math.ceil(dur / max_duration))
    words = text.split()
    if len(words) <= k:
        slices = [[w] for w in words]
    else:
        N = len(words)
        is_punct = [bool(re.search(r'[.!?—,;:]$', w)) for w in words]
        cuts = [0]
        for c in range(1, k):
            ideal = c * (N / k)
            min_pos = cuts[-1] + 1
            max_pos = N - (k - c)
            best_pos = round(ideal)
            best_pos = max(min_pos, min(max_pos, best_pos))
            punct_cands = [p for p in range(max(min_pos, best_pos - 2), min(max_pos + 1, best_pos + 3)) if is_punct[p - 1]]
            if punct_cands:
                best_pos = min(punct_cands, key=lambda p: abs(p - ideal))
            cuts.append(best_pos)
        cuts.append(N)
        slices = [words[cuts[i]:cuts[i+1]] for i in range(len(cuts) - 1)]

    slice_texts = [" ".join(s) for s in slices if s]
    raw_lens = [max(1, len(re.sub(r'\s+', '', st))) for st in slice_texts]
    tot_len = sum(raw_lens) or 1

    result = []
    cur = start_t
    for idx, (st, l) in enumerate(zip(slice_texts, raw_lens)):
        span = (l / tot_len) * dur
        span = min(max_duration, span)
        s_end = cur + span
        if idx == len(slice_texts) - 1:
            s_end = end_t
        result.append({"text": st, "start": cur, "end": s_end})
        cur = s_end
    return result


def generate_srt(text: str, duration: float, output_path: str, timed_segments: Optional[List[dict]] = None) -> None:
    """
    Generate an SRT subtitle file from transcript text and audio duration.
    If timed_segments from actual synthesis audio buffers is provided,
    writes exact acoustically accurate timestamps. Otherwise falls back to
    mathematical distribution.
    """
    try:
        import math
        import re
        from pathlib import Path
        srt_file = Path(output_path).parent / "transcript.srt"

        if duration <= 0 or not text or not text.strip():
            srt_file.write_text("", encoding="utf-8")
            return

        def _fmt_time(s: float) -> str:
            s = max(0.0, s)
            ms = int(round((s % 1) * 1000))
            if ms >= 1000:
                ms = 999
            si = int(s)
            h = si // 3600
            m = (si % 3600) // 60
            sec = si % 60
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        if timed_segments:
            # Flatten & ensure each segment is <= 3.0s
            norm_segments = []
            for seg in timed_segments:
                norm_segments.extend(
                    split_segment_if_needed(seg["text"], float(seg["start"]), float(seg["end"]))
                )
            srt_lines = []
            for idx, seg in enumerate(norm_segments, 1):
                start_t = float(seg.get("start", 0.0))
                end_t = float(seg.get("end", start_t + 1.0))
                txt = str(seg.get("text", "")).strip()
                if not txt:
                    continue
                srt_lines.append(str(idx))
                srt_lines.append(f"{_fmt_time(start_t)} --> {_fmt_time(end_t)}")
                srt_lines.append(txt)
                srt_lines.append("")
            srt_file.write_text("\n".join(srt_lines), encoding="utf-8")
            from core.logger import log
            log.info(f"Generated acoustically accurate SRT from synthesis buffers: {srt_file} ({len(norm_segments)} chunks)")
            generate_chapters_from_tts(text, duration, srt_file.parent, timed_segments=norm_segments)
            return

        cleaned_text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        words = [w for w in cleaned_text.split(" ") if w]
        if not words:
            srt_file.write_text("", encoding="utf-8")
            return

        # Determine optimal number of chunks K
        # Each chunk duration must be <= 3.0s, so K >= ceil(duration / 3.0)
        # Natural cadence targets 2.0 - 3.0s (average ~2.5s)
        min_chunks = max(1, math.ceil(duration / 3.0))
        desired_chunks = max(min_chunks, round(duration / 2.5))
        num_chunks = min(len(words), desired_chunks)
        num_chunks = max(min_chunks, num_chunks)

        # 1. Partition words into num_chunks slices respecting punctuation (. , ! ? ; : —)
        if num_chunks <= 1 or len(words) <= 1:
            chunk_word_lists = [words]
        elif len(words) <= num_chunks:
            chunk_word_lists = [[w] for w in words]
        else:
            N = len(words)
            K = num_chunks
            is_punct = [bool(re.search(r'[.!?—,;:]$', w)) for w in words]
            cuts = [0]
            for c in range(1, K):
                ideal = c * (N / K)
                min_pos = cuts[-1] + 1
                max_pos = N - (K - c)
                best_pos = round(ideal)
                best_pos = max(min_pos, min(max_pos, best_pos))

                # Check for nearby punctuation
                punct_candidates = [
                    p for p in range(max(min_pos, best_pos - 2), min(max_pos + 1, best_pos + 3))
                    if is_punct[p - 1]
                ]
                if punct_candidates:
                    best_pos = min(punct_candidates, key=lambda p: abs(p - ideal))

                cuts.append(best_pos)
            cuts.append(N)

            chunk_word_lists = [words[cuts[i]:cuts[i+1]] for i in range(len(cuts) - 1)]

        chunk_texts = [" ".join(cw) for cw in chunk_word_lists if cw]
        if not chunk_texts:
            chunk_texts = [cleaned_text]
        k_actual = len(chunk_texts)

        # 2. Compute chunk durations strictly <= 3.0s with natural 2.0-3.0s rhythm variation
        if k_actual <= 1:
            durations = [min(3.0, duration)]
        else:
            targets = [2.4, 2.8, 2.2, 2.9, 2.5, 3.0, 2.3, 2.7]
            raw_targets = [targets[i % len(targets)] for i in range(k_actual)]
            tot_raw = sum(raw_targets) or 1.0
            scaled = [(r / tot_raw) * duration for r in raw_targets]

            # Iterative clamp and redistribution so no chunk exceeds 3.0s
            for _ in range(30):
                excess = 0.0
                unclamped = []
                for i, d in enumerate(scaled):
                    if d > 3.0:
                        excess += (d - 3.0)
                        scaled[i] = 3.0
                    elif d < 3.0:
                        unclamped.append(i)
                if excess <= 0.0001 or not unclamped:
                    break
                add_per = excess / len(unclamped)
                for i in unclamped:
                    scaled[i] += add_per

            # Adjust for floating point inaccuracies to guarantee exact duration match & <= 3.0s
            diff = duration - sum(scaled)
            for i in range(k_actual - 1, -1, -1):
                if diff > 0 and scaled[i] < 3.0:
                    room = 3.0 - scaled[i]
                    add = min(room, diff)
                    scaled[i] += add
                    diff -= add
                elif diff < 0 and scaled[i] > 0.5:
                    room = scaled[i] - 0.5
                    sub = min(room, -diff)
                    scaled[i] -= sub
                    diff += sub

            durations = scaled

        def _fmt_time(s: float) -> str:
            s = max(0.0, s)
            ms = int(round((s % 1) * 1000))
            if ms >= 1000:
                ms = 999
            si = int(s)
            h = si // 3600
            m = (si % 3600) // 60
            sec = si % 60
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        srt_lines = []
        cur_t = 0.0
        for idx, chunk in enumerate(chunk_texts, 1):
            start_t = cur_t
            dur = durations[idx - 1] if idx - 1 < len(durations) else 2.5
            dur = min(3.0, dur)  # Strict hard cap <= 3.0s
            end_t = min(duration, start_t + dur)
            if idx == len(chunk_texts):
                if duration - start_t <= 3.0:
                    end_t = duration

            cur_t = end_t
            srt_lines.append(str(idx))
            srt_lines.append(f"{_fmt_time(start_t)} --> {_fmt_time(end_t)}")
            srt_lines.append(chunk)
            srt_lines.append("")

        srt_file.write_text("\n".join(srt_lines), encoding="utf-8")
        from core.logger import log
        log.info(f"Generated SRT file successfully: {srt_file}")
        generate_chapters_from_tts(text, duration, srt_file.parent, timed_segments=None)
    except Exception as e:
        from core.logger import log
        log.error(f"Failed to generate SRT file: {e}")


def generate_chapters_from_tts(text: str, duration: float, output_dir: Path, timed_segments: Optional[List[dict]] = None) -> None:
    """
    Extracts chapters from script text or project.json and saves chapters.txt with accurate timestamps.
    """
    try:
        import json
        import re
        from pathlib import Path

        output_dir = Path(output_dir)
        # Check script text for [Chapter: Title]
        chapter_pattern = re.compile(
            r'(?:^|\n)\s*(?:\[\s*(?:Chapter|CHAPTER)(?:\s*\d+)?:\s*([^\]]+)\]|#*\s*(?:Chapter|CHAPTER)\s+\d+[:\-]\s*([^\n]+))\s*(?:\n|\Z)',
            re.IGNORECASE
        )
        matches = list(chapter_pattern.finditer(text))
        raw_chapters = []

        if matches:
            for i, match in enumerate(matches):
                raw_title = match.group(1) or match.group(2) or f"Chapter {i+1}"
                title = raw_title.strip()
                start_pos = match.end()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[start_pos:end_pos].strip()
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', body) if s.strip()]
                first_sent = sentences[0] if sentences else body[:100]
                raw_chapters.append({"title": title, "first_sentence": first_sent})
        else:
            # Check project.json
            pjson = output_dir / "project.json"
            if not pjson.exists():
                pjson = output_dir / "metadata.json"
            if pjson.exists():
                try:
                    pdata = json.loads(pjson.read_text(encoding="utf-8"))
                    for ch in pdata.get("chapters", []):
                        if isinstance(ch, dict):
                            raw_chapters.append({"title": ch.get("title", "Chapter"), "first_sentence": ch.get("first_sentence", "")})
                except Exception:
                    pass

        if not raw_chapters:
            return

        # Load segments from timed_segments or transcript.srt
        segments = []
        if timed_segments:
            for seg in timed_segments:
                segments.append({"start": float(seg.get("start", 0.0)), "text": str(seg.get("text", ""))})
        else:
            srt_path = output_dir / "transcript.srt"
            if srt_path.exists():
                srt_content = srt_path.read_text(encoding="utf-8", errors="replace")
                m_segs = re.finditer(r'(\d+):(\d+):(\d+)[,\.](\d+)\s*-->.*?\n(.*?)(?=\n\s*\n|\Z)', srt_content, re.DOTALL)
                for sm in m_segs:
                    st = int(sm.group(1))*3600 + int(sm.group(2))*60 + int(sm.group(3)) + int(sm.group(4))/1000.0
                    segments.append({"start": st, "text": sm.group(5).strip()})

        # Match timestamps
        final_chapters = []
        prev_s = 0.0
        use_hours = (duration >= 3600.0)

        for idx, ch in enumerate(raw_chapters):
            title = ch["title"]
            first_sent = ch.get("first_sentence", "")
            if idx == 0:
                chap_s = 0.0
            else:
                min_allowed = prev_s + 10.0
                target_words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', ' ', first_sent.lower()).split() if w][:8]
                matched_t = None
                if target_words and segments:
                    w_set = set(target_words)
                    for seg in segments:
                        if seg["start"] >= min_allowed - 1.0:
                            s_words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', ' ', seg["text"].lower()).split() if w]
                            if sum(1 for tw in target_words if tw in s_words) >= max(1, len(target_words) // 2):
                                matched_t = seg["start"]
                                break
                if matched_t is not None and matched_t >= min_allowed:
                    chap_s = matched_t
                else:
                    prop = (idx / float(len(raw_chapters))) * duration if duration > 0 else min_allowed
                    chap_s = max(min_allowed, round(prop, 1))

            prev_s = chap_s
            tot_i = int(round(chap_s))
            h = tot_i // 3600
            m = (tot_i % 3600) // 60
            s = tot_i % 60
            ts_str = f"{h:02d}:{m:02d}:{s:02d}" if (use_hours or h > 0) else f"{m:02d}:{s:02d}"
            final_chapters.append(f"{ts_str} - {title}")

        chapters_file = output_dir / "chapters.txt"
        chapters_file.write_text("\n".join(final_chapters) + "\n", encoding="utf-8")

        proj_json = output_dir / "project.json"
        if proj_json.exists():
            try:
                import json
                pdata = json.loads(proj_json.read_text(encoding="utf-8"))
                pdata["chapters"] = [
                    {"title": ch["title"], "timestamp": final_chapters[i].split(" - ", 1)[0], "seconds": float(i * 10)}
                    for i, ch in enumerate(raw_chapters)
                ]
                cur_desc = pdata.get("seo_description", "")
                if cur_desc and "00:00" not in cur_desc and final_chapters:
                    pdata["seo_description"] = cur_desc.rstrip() + "\n\nTimestamps:\n" + "\n".join(final_chapters)
                proj_json.write_text(json.dumps(pdata, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        from core.logger import log
        log.info(f"Generated YouTube chapters file from TTS: {chapters_file}")
    except Exception as e:
        from core.logger import log
        log.warning(f"Could not generate chapters from TTS: {e}")


def master_audio(samples: np.ndarray, sr: int, target_peak: float = 0.95) -> np.ndarray:
    """
    Broadcast audio mastering: normalizes audio to target peak (-0.45 dBFS)
    to prevent clipping and ensure consistent, professional loudness.
    """
    if samples is None or len(samples) == 0:
        return samples
    max_val = float(np.max(np.abs(samples)))
    if max_val > 1e-6:
        samples = samples * (target_peak / max_val)
    return np.clip(samples, -1.0, 1.0)


# Fixed multi-word proper terms, technology concepts, and compound expressions
# that should be spoken together in one natural breath rather than broken up
COMMON_COMPOUND_PHRASES = [
    # ── Internet, Computing, and Modern Technology ──────────────────────────
    (r'\b(world|World|word|Word)\s*[- ]\s*(wide|Wide)\s*[- ]\s*(web|Web)\b',
     lambda m: "World-Wide-Web" if m.group(1)[0].isupper() else "world-wide-web"),
    (r'\b(worldwide|Worldwide)\s*[- ]\s*(web|Web)\b',
     lambda m: "World-Wide-Web" if m.group(1)[0].isupper() else "world-wide-web"),
    (r'\b(open|Open)\s+(source|Source)\b', r'\1-\2'),
    (r'\b(machine|Machine)\s+(learning|Learning)\b', r'\1-\2'),
    (r'\b(artificial|Artificial)\s+(intelligence|Intelligence)\b', r'\1-\2'),
    (r'\b(deep|Deep)\s+(learning|Learning)\b', r'\1-\2'),
    (r'\b(neural|Neural)\s+(networks?|Networks?)\b', r'\1-\2'),
    (r'\b(large|Large)\s+(language|Language)\s+(models?|Models?)\b', r'\1-\2-\3'),
    (r'\b(reinforcement|Reinforcement)\s+(learning|Learning)\b', r'\1-\2'),
    (r'\b(feed|Feed)\s+(forward|Forward)\b', r'\1-\2'),
    (r'\b(self|Self)\s+(attention|Attention)\b', r'\1-\2'),
    (r'\b(data|Data)\s+(centers?|centres?|Centers?|Centres?)\b', r'\1-\2'),
    (r'\b(computer|Computer)\s+(science|Science)\b', r'\1-\2'),
    (r'\b(real|Real)\s+(time|Time)\b', r'\1-\2'),
    (r'\b(high|High)\s+(tech|Tech)\b', r'\1-\2'),
    (r'\b(high|High)\s+(speed|Speed)\b', r'\1-\2'),
    (r'\b(cloud|Cloud)\s+(native|Native)\b', r'\1-\2'),
    (r'\b(cutting|Cutting)\s+(edge|Edge)\b', r'\1-\2'),
    (r'\b(state|State)\s+of\s+the\s+(art|Art)\b', r'\1-of-the-\2'),

    # ── Media, Culture, and Social Concepts ───────────────────────────────────
    (r'\b(social|Social)\s+(media|Media)\b', r'\1-\2'),
    (r'\b(rock|Rock)\s*(?:and|&|\'n\'|\'n)\s*(roll|Roll)\b', r'\1-and-\2'),
    (r'\b(rocknroll|Rocknroll)\b', lambda m: "Rock-and-Roll" if m.group(1)[0].isupper() else "rock-and-roll"),
    (r'\b(hip|Hip)\s+(hop|Hop)\b', r'\1-\2'),

    # ── Fixed Idiomatic & Common Compound Expressions ────────────────────────
    (r'\b(high|High)\s+(school|School)\b', r'\1-\2'),
    (r'\b(post|Post)\s+(office|Office)\b', r'\1-\2'),
    (r'\b(point|Point)\s+of\s+(view|View)\b', r'\1-of-\2'),
    (r'\b(out|Out)\s+of\s+(date|Date)\b', r'\1-of-\2'),
    (r'\b(up|Up)\s+to\s+(date|Date)\b', r'\1-to-\2'),
    (r'\b(part|Part)\s+of\s+(speech|Speech)\b', r'\1-of-\2'),
    (r'\b(step|Step)\s+by\s+(step|Step)\b', r'\1-by-\2'),
    (r'\b(back|Back)\s+and\s+(forth|Forth)\b', r'\1-and-\2'),
    (r'\b(front|Front)\s+and\s+(center|Center|centre|Centre)\b', r'\1-and-\2'),
    (r'\b(by|By)\s+and\s+(large|Large)\b', r'\1-and-\2'),
    (r'\b(first|First)\s+and\s+(foremost|Foremost)\b', r'\1-and-\2'),
    (r'\b(sooner|Sooner)\s+or\s+(later|Later)\b', r'\1-or-\2'),
    (r'\b(day|Day)\s+in\s+and\s+day\s+(out|Out)\b', r'\1-in-and-day-\2'),
    (r'\b(on|On)\s+the\s+other\s+(hand|Hand)\b', r'\1-the-other-\2'),
    (r'\b(as|As)\s+a\s+matter\s+of\s+(fact|Fact)\b', r'\1-a-matter-of-\2'),
    (r'\b(in|In)\s+the\s+(meantime|Meantime)\b', r'\1-the-\2'),
    (r'\b(at|At)\s+the\s+end\s+of\s+the\s+(day|Day)\b', r'\1-the-end-of-the-\2'),
    (r'\b(ad|Ad)\s+(hoc|Hoc)\b', r'\1-\2'),
    (r'\b(vice|Vice)\s+(versa|Versa)\b', r'\1-\2'),
    (r'\b(status|Status)\s+(quo|Quo)\b', r'\1-\2'),

    # ── Well-known Places and Geographic Names ───────────────────────────────
    (r'\b(Silicon|silicon)\s+(Valley|valley)\b', r'\1-\2'),
    (r'\b(United|united)\s+(States|states)\b', r'\1-\2'),
    (r'\b(New|new)\s+(York|york)\b', r'\1-\2'),
    (r'\b(Wall|wall)\s+(Street|street)\b', r'\1-\2'),
    (r'\b(South|south)\s+(Bronx|bronx)\b', r'\1-\2'),
    (r'\b(West|west)\s+(Bronx|bronx)\b', r'\1-\2'),
    (r'\b(San|san)\s+(Francisco|francisco)\b', r'\1-\2'),
    (r'\b(Los|los)\s+(Angeles|angeles)\b', r'\1-\2'),
    (r'\b(Hong|hong)\s+(Kong|kong)\b', r'\1-\2'),
    (r'\b(North|north)\s+(America|america)\b', r'\1-\2'),
    (r'\b(South|south)\s+(America|america)\b', r'\1-\2'),

    # ── Number Compounds ──────────────────────────────────────────────────────
    (r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\s+(one|two|three|four|five|six|seven|eight|nine)\b', r'\1-\2'),
    (r'\b(Twenty|Thirty|Forty|Fifty|Sixty|Seventy|Eighty|Ninety)\s+(one|two|three|four|five|six|seven|eight|nine)\b', r'\1-\2'),
]


def preprocess_text_for_pacing(text: str) -> str:
    """
    Enhance natural pauses, breathing room, punctuation cadence,
    and compound phrase cohesion for human-like narration:
    1. Reconnects hyphenated compounds separated by spaces (e.g. 'word -wide' -> 'word-wide').
    2. Converts raw double/triple dashes ('--') into proper em-dashes (' — ') with breathing room.
    3. Normalizes ellipses ('...' / '…') to uniform pause markers with breathing space.
    4. Ensures compound terms (e.g. 'world-wide-web', 'artificial-intelligence') are cohesive
       so the TTS model speaks them smoothly in the same breath without disjointed pauses.
    5. Formats clause punctuation (; and :) for natural rhythmic pauses.
    6. Formats introductory transition phrases (e.g. 'However,', 'In fact,') to ensure natural cadence.
    7. Standardizes quotation marks and cleans up abnormal spacing.
    """
    if not text:
        return ""

    import re

    # 1. Normalize line breaks and tabs
    text = re.sub(r"\r\n|\r", "\n", text)

    # 1.5 Strip chapter markers (e.g. [Chapter: ...], [Chapter 1: ...]) from voiceover so TTS speaks only pure narration
    text = re.sub(r'\[\s*(?:Chapter|CHAPTER)(?:\s*\d+)?:\s*[^\]]+\]', '\n\n', text)

    # 2. Fix spaced hyphens between alphanumeric words/numbers:
    # e.g., 'word -wide' -> 'word-wide', 'break -in' -> 'break-in', 'eighteen -year -old' -> 'eighteen-year-old'
    text = re.sub(r"(\b[A-Za-z0-9]+)\s*-\s*([A-Za-z0-9]+\b)", r"\1-\2", text)

    # 3. Handle double or triple dashes: 'word wide -- web' or 'word wide---web' -> convert to em-dash ' — '
    text = re.sub(r"\s*--+\s*", " — ", text)

    # 4. Standardize em-dashes and en-dashes with surrounding space so TTS pauses naturally
    text = re.sub(r"\s*[—–]\s*", " — ", text)

    # 5. Connect known fixed multi-word terms and compound phrases so they are spoken
    # in the same breath without disjointed pauses or awkward chunk boundaries
    for pattern, repl in COMMON_COMPOUND_PHRASES:
        text = re.sub(pattern, repl, text)

    # 6. Normalize ellipses (... or …) to uniform marker followed by space for natural breath
    text = re.sub(r"(\.{3,}|…)\s*", r"... ", text)

    # 7. Normalize semicolons and colons to have clean single trailing space for natural clause cadence
    text = re.sub(r"\s*([;:])\s*", r"\1 ", text)

    # 8. Ensure clean single-space after commas
    text = re.sub(r"\s*,\s*", ", ", text)

    # 9. Format introductory transition phrases to have natural trailing comma if omitted
    # e.g. "However the system" -> "However, the system", "In fact it was" -> "In fact, it was"
    text = re.sub(
        r'(^|(?<=[.!?;\n]\s))(However|Furthermore|Moreover|Nevertheless|Specifically|Consequently|Meanwhile|Suddenly|Interestingly|Surprisingly|In fact|For example|For instance|That is|In other words|On the contrary)\s+([A-Za-z])',
        r'\1\2, \3',
        text
    )

    # 10. Normalize fancy quote characters
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    # 11. Clean up extra horizontal whitespace while preserving paragraph breaks
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def preprocess_text_pacing(text: str) -> str:
    """Alias for backward compatibility."""
    return preprocess_text_for_pacing(text)


def _split_long_sentence_at_clauses(sent: str, limit: int) -> List[str]:
    """
    Split a sentence that exceeds `limit` characters at natural syntactic/clause boundaries:
    1. Semicolons and colons (; :)
    2. Em-dashes and en-dashes (— –)
    3. Commas (,)
    4. Coordinating conjunctions and clause markers (and, but, which, that, because, etc.)
    5. Safe word boundaries as last resort
    """
    import re
    sent = sent.strip()
    if len(sent) <= limit:
        return [sent]

    clause_delimiters = [
        r'(?<=[;:])\s+',
        r'(?<=[—–])\s*',
        r'(?<=,)\s+',
        r'\s+(?=(?:and|but|or|nor|for|yet|so|which|that|because|although|when|where|while|since)\b)',
        r'\s+'
    ]

    for delim in clause_delimiters:
        parts = [p.strip() for p in re.split(delim, sent) if p.strip()]
        if len(parts) > 1 and all(len(p) <= limit for p in parts):
            packed: List[str] = []
            cur = ""
            for p in parts:
                cand = (cur + " " + p).strip() if cur else p
                if len(cand) <= limit:
                    cur = cand
                else:
                    if cur:
                        packed.append(cur)
                    cur = p
            if cur:
                packed.append(cur)
            if all(len(p) <= limit for p in packed):
                return packed

    for delim in clause_delimiters:
        parts = [p.strip() for p in re.split(delim, sent) if p.strip()]
        if len(parts) > 1:
            packed = []
            cur = ""
            for p in parts:
                if len(p) > limit:
                    if cur:
                        packed.append(cur)
                        cur = ""
                    packed.extend(_split_long_sentence_at_clauses(p, limit))
                else:
                    cand = (cur + " " + p).strip() if cur else p
                    if len(cand) <= limit:
                        cur = cand
                    else:
                        if cur:
                            packed.append(cur)
                        cur = p
            if cur:
                packed.append(cur)
            return packed

    # Ultimate fallback: word slice
    words = sent.split()
    chunks: List[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if len(cand) <= limit:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = w
    if cur:
        chunks.append(cur)
    return chunks


def chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT, smart_pacing: bool = True) -> List[str]:
    """
    Split text into sentence- and clause-aligned chunks each ≤ *limit* characters.
    Never splits fixed multi-word phrases mid-breath.
    Preserves paragraph boundaries and ensures natural breathing room between thoughts.
    """
    import re
    if smart_pacing:
        text = preprocess_text_for_pacing(text)

    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if not paragraphs:
        return [text]

    chunks: List[str] = []

    # Protected abbreviations and titles regex so genuine sentences aren't split prematurely
    abbrevs = [
        r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Gen|Col|Capt|Lt|St)\.',
        r'\b(?:U\.S|U\.K|U\.S\.A|e\.g|i\.e|etc|vs|approx|est|dept|vol)\.',
        r'\b\d+\.\d+\b',
        r'\b[A-Za-z]\.',
        r'\b(?:a\.m|p\.m)\.'
    ]

    for p_idx, para in enumerate(paragraphs):
        is_last_para = (p_idx == len(paragraphs) - 1)

        protected_para = para
        for pat in abbrevs:
            protected_para = re.sub(
                pat,
                lambda m: m.group(0).replace('.', '\u2024'),
                protected_para,
                flags=re.IGNORECASE
            )

        sent_parts = re.split(r'(?<=[.!?])\s+', protected_para)
        sentences = [sp.replace('\u2024', '.').strip() for sp in sent_parts if sp.strip()]
        if not sentences:
            sentences = [para]

        para_chunks: List[str] = []

        if smart_pacing:
            # Under smart pacing, each sentence is synthesized with natural breathing room
            # unless a long sentence exceeds limit, in which case it is split at clauses
            for sent in sentences:
                if len(sent) > limit:
                    sub_chunks = _split_long_sentence_at_clauses(sent, limit)
                    for sc in sub_chunks:
                        if len(sc) > limit:
                            for i in range(0, len(sc), limit):
                                para_chunks.append(sc[i:i+limit])
                        else:
                            para_chunks.append(sc)
                else:
                    para_chunks.append(sent)
        else:
            # Legacy packing mode
            cur = ""
            for sent in sentences:
                if len(sent) > limit:
                    if cur:
                        para_chunks.append(cur)
                        cur = ""
                    sub_chunks = _split_long_sentence_at_clauses(sent, limit)
                    for sc in sub_chunks:
                        if len(sc) > limit:
                            for i in range(0, len(sc), limit):
                                para_chunks.append(sc[i:i+limit])
                        else:
                            cand = (cur + " " + sc).strip() if cur else sc
                            if len(cand) <= limit:
                                cur = cand
                            else:
                                if cur:
                                    para_chunks.append(cur)
                                cur = sc
                else:
                    cand = (cur + " " + sent).strip() if cur else sent
                    if len(cand) <= limit:
                        cur = cand
                    else:
                        if cur:
                            para_chunks.append(cur)
                        cur = sent
            if cur:
                para_chunks.append(cur)

        # Mark the last chunk of a non-final paragraph with a trailing newline
        # so calculate_chunk_pause knows to award a full paragraph transition pause
        if para_chunks:
            if not is_last_para:
                para_chunks[-1] = para_chunks[-1].rstrip() + "\n"
            chunks.extend(para_chunks)

    return chunks or [text]


def concat_wavs(paths: List[str], out: str, pauses: Optional[List[float]] = None) -> None:
    """
    Concatenate multiple WAV files into one.
    If `pauses` is provided (list of pause durations in seconds between consecutive files),
    inserts calibrated digital silence frames for natural breathing pauses.
    """
    if not paths:
        return
    params = None
    frames = []
    sr = SAMPLE_RATE
    for p in paths:
        with wave.open(p, "rb") as wf:
            if not params:
                params = wf.getparams()
                sr = wf.getframerate()
            frames.append(wf.readframes(wf.getnframes()))
    if not params:
        return
    with wave.open(out, "wb") as wf:
        wf.setparams(params)
        for i, f in enumerate(frames):
            wf.writeframes(f)
            if pauses and i < len(pauses) and pauses[i] > 0:
                silence_frames = int(round(pauses[i] * sr))
                silence_bytes = b"\x00" * (silence_frames * params.nchannels * params.sampwidth)
                wf.writeframes(silence_bytes)


def calculate_chunk_pause(chunk_text: str, default_pause: float = 0.38) -> float:
    """
    Determine the optimal natural breathing pause after a chunk based on its terminating punctuation:
    - Paragraph end (indicated by trailing newline '\\n'): 0.65s thematic paragraph transition
    - Strong pause (… or ...): 0.48s reflective/dramatic pause
    - Sentence end (. ! ?): 0.38s natural human breath pause (or `default_pause`)
    - Em-dash or colon (— or :): 0.24s suspension pause
    - Semicolon or comma (; or ,): 0.15s clause breath pause
    - Mid-clause / no punctuation: 0.06s subtle micro-gap (prevents abrupt syllable clipping)
    """
    if not chunk_text:
        return 0.0
    if chunk_text.endswith(("\n", "\r\n")) or "\n" in chunk_text:
        return 0.65
    ct = chunk_text.rstrip()
    if not ct:
        return 0.0
    if ct.endswith(("...", "…")):
        return 0.48
    if ct.endswith((".", "!", "?")):
        return default_pause
    if ct.endswith(("—", "–", ":")):
        return 0.24
    if ct.endswith((";", ",")):
        return 0.15
    return 0.06


class TTSEngine:
    """
    Multi-backend TTS engine supporting Kokoro, Piper, and Edge-TTS.
    """

    def __init__(self):
        self._kokoro = None
        self._piper_voices = {}

    def _load_kokoro(self):
        if self._kokoro is not None:
            return
        if not MODEL_FILE.exists() or not VOICES_FILE.exists():
            raise RuntimeError("Kokoro model files not found. Please restart app.")
        log.step(f"Loading Kokoro ONNX model from {MODEL_FILE}…")
        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(str(MODEL_FILE), str(VOICES_FILE))
        log.info("Kokoro loaded successfully.")

    def synthesize(
        self,
        text: str,
        out_path: str,
        voice: str,
        speed: float = 1.0,
        chunk_limit: int = CHUNK_CHAR_LIMIT,
        cb: Optional[Callable[[str], None]] = None,
    ) -> List[dict]:
        resolved_voice = resolve_voice(voice)
        cfg = VOICE_CATALOGUE.get(resolved_voice, next(iter(VOICE_CATALOGUE.values())))
        backend = cfg.get("backend", "kokoro")

        if backend == "kokoro":
            return self._synth_kokoro(text, out_path, cfg, speed, chunk_limit, cb)
        elif backend == "piper":
            return self._synth_piper(text, out_path, cfg, speed, chunk_limit, cb)
        elif backend == "edgetts":
            return self._synth_edgetts(text, out_path, cfg, speed, cb)
        elif backend == "elevenlabs":
            return self._synth_elevenlabs(text, out_path, cfg, speed, chunk_limit, cb)
        else:
            raise ValueError(f"Unknown TTS backend: {backend}")

    def _synth_kokoro(self, text, out_path, cfg, speed, chunk_limit, cb) -> List[dict]:
        v_id = cfg["id"]
        lang = cfg["lang"]

        # Load user settings for enhancements
        import config.settings as CFG
        user_cfg = CFG.load()
        do_mastering = user_cfg.get("enhance_audio", True)
        smart_pacing = user_cfg.get("smart_pacing", True)

        log.step(f"Kokoro Synthesis — voice='{v_id}' lang='{lang}' speed={speed}x (mastering={do_mastering})")
        if cb: cb("Loading Kokoro…")
        self._load_kokoro()

        chunks = chunk_text(text, limit=chunk_limit, smart_pacing=smart_pacing)

        # Check voice blending
        blend_ratio = user_cfg.get("blend_voice_ratio", 0.0)
        v_id_2 = user_cfg.get("secondary_voice", "")

        # Kokoro supports blending voices by passing styling weights or arrays
        # If blend is configured, we pass both. Otherwise, just one.
        # Ensure we always pass string voice unless the library supports blended arrays
        # (Kokoro allows combining styles externally, but for standard ONNX we'll stick to string for now.
        # Future enhancement: extracting `voice_tensor` and mixing them manually before `create()`)

        if len(chunks) == 1:
            if cb: cb("Synthesising…")
            clean_single = chunks[0].strip()
            samples, sr = self._kokoro.create(clean_single, voice=v_id, speed=speed, lang=lang)
            if do_mastering:
                samples = master_audio(samples, sr)
            sf.write(out_path, samples, sr, format='WAV', subtype="PCM_16")
            dur = len(samples) / float(sr)
            return [{"text": clean_single, "start": 0.0, "end": dur}]

        tmps = []
        timed_segments = []
        pauses = []
        cur_t = 0.0
        try:
            for i, chunk in enumerate(chunks, 1):
                clean_chunk = chunk.strip()
                if not clean_chunk:
                    continue
                if cb: cb(f"Chunk {i}/{len(chunks)}")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                samples, sr = self._kokoro.create(clean_chunk, voice=v_id, speed=speed, lang=lang)
                if do_mastering:
                    samples = master_audio(samples, sr)
                sf.write(tmp, samples, sr, format='WAV', subtype="PCM_16")
                tmps.append(tmp)
                seg_dur = len(samples) / float(sr)
                timed_segments.append({
                    "text": clean_chunk,
                    "start": cur_t,
                    "end": cur_t + seg_dur
                })
                cur_t += seg_dur

                # Calculate natural inter-chunk pause if more chunks follow
                if i < len(chunks):
                    p_dur = calculate_chunk_pause(chunk) if smart_pacing else 0.0
                    pauses.append(p_dur)
                    cur_t += p_dur

            if cb: cb("Merging audio…")
            concat_wavs(tmps, out_path, pauses=pauses)
            return timed_segments
        finally:
            for p in tmps:
                try: os.remove(p)
                except OSError: pass

    def _synth_piper(self, text, out_path, cfg, speed, chunk_limit, cb) -> List[dict]:
        v_id = cfg["id"]
        log.step(f"Piper Synthesis — voice='{v_id}' speed={speed}x")
        if cb: cb("Downloading/Checking Piper model…")

        ok, model_p, json_p = ensure_piper_voice_downloaded(cfg, cb)
        if not ok:
            raise RuntimeError(f"Failed to download Piper voice model {v_id}")

        from piper import PiperVoice
        voice_key = str(model_p)
        if voice_key not in self._piper_voices:
            if cb: cb("Loading Piper voice into memory…")
            self._piper_voices[voice_key] = PiperVoice.load(str(model_p), config_path=str(json_p), use_cuda=False)

        voice_inst = self._piper_voices[voice_key]

        import config.settings as CFG_mod
        user_cfg = CFG_mod.load()
        smart_pacing = user_cfg.get("smart_pacing", True)

        chunks = chunk_text(text, limit=chunk_limit, smart_pacing=smart_pacing)
        tmps = []
        timed_segments = []
        pauses = []
        cur_t = 0.0
        try:
            for i, chunk in enumerate(chunks, 1):
                clean_chunk = chunk.strip()
                if not clean_chunk:
                    continue
                if cb: cb(f"Synthesising chunk {i}/{len(chunks)}")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                with wave.open(tmp, "wb") as wav_file:
                    voice_inst.synthesize(clean_chunk, wav_file, length_scale=1.0/speed)
                tmps.append(tmp)
                with wave.open(tmp, "rb") as wf:
                    seg_dur = float(wf.getnframes()) / float(wf.getframerate())
                timed_segments.append({
                    "text": clean_chunk,
                    "start": cur_t,
                    "end": cur_t + seg_dur
                })
                cur_t += seg_dur
                if i < len(chunks):
                    p_dur = calculate_chunk_pause(chunk) if smart_pacing else 0.0
                    pauses.append(p_dur)
                    cur_t += p_dur
            if cb: cb("Merging audio…")
            concat_wavs(tmps, out_path, pauses=pauses)
            return timed_segments
        finally:
            for p in tmps:
                try: os.remove(p)
                except OSError: pass

    def _synth_edgetts(self, text, out_path, cfg, speed, cb) -> List[dict]:
        v_id = cfg["id"]
        log.step(f"Edge-TTS Synthesis — voice='{v_id}' speed={speed}x")
        if cb: cb("Connecting to Edge-TTS…")

        import config.settings as CFG_mod
        app_cfg = CFG_mod.load()
        if app_cfg.get("smart_pacing", True):
            text = preprocess_text_for_pacing(text)

        import edge_tts

        # Edge rate format: "+0%" or "+50%" or "-20%"
        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"

        timed_segments: List[dict] = []

        async def _run():
            nonlocal timed_segments
            submaker = edge_tts.SubMaker()
            communicate = edge_tts.Communicate(text, v_id, rate=rate_str)
            # Temporary mp3 file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_mp3 = tf.name

            try:
                with open(tmp_mp3, "wb") as f:
                    async for message in communicate.stream():
                        if message["type"] == "audio":
                            f.write(message["data"])
                        elif message["type"] == "WordBoundary":
                            submaker.feed(message)

                # Check if file has audio data
                if not os.path.exists(tmp_mp3) or os.path.getsize(tmp_mp3) == 0:
                    raise RuntimeError("No audio received from Edge-TTS service.")

                # Convert MP3 to WAV / or save directly if soundfile or ffmpeg available
                # If output is .wav, convert mp3 to wav via soundfile
                import soundfile as sf
                data, samplerate = sf.read(tmp_mp3)

                # Master audio if enabled
                import config.settings as CFG_mod
                app_cfg = CFG_mod.load()
                if app_cfg.get("enhance_audio", True):
                    data = master_audio(data, samplerate)

                sf.write(out_path, data, samplerate, subtype="PCM_16")

                # If submaker captured cues, group into <= 3s segments
                if submaker.cues:
                    cur_group = []
                    group_start = 0.0
                    for cue in submaker.cues:
                        c_start = cue.start.total_seconds()
                        c_end = cue.end.total_seconds()
                        c_text = cue.content
                        if not cur_group:
                            group_start = c_start
                            cur_group.append((c_text, c_end))
                        elif c_end - group_start <= 3.0:
                            cur_group.append((c_text, c_end))
                        else:
                            timed_segments.append({
                                "text": " ".join(t[0] for t in cur_group),
                                "start": group_start,
                                "end": cur_group[-1][1]
                            })
                            group_start = c_start
                            cur_group = [(c_text, c_end)]
                    if cur_group:
                        timed_segments.append({
                            "text": " ".join(t[0] for t in cur_group),
                            "start": group_start,
                            "end": cur_group[-1][1]
                        })
                else:
                    tot_dur = len(data) / float(samplerate)
                    timed_segments.append({"text": text, "start": 0.0, "end": tot_dur})
            finally:
                if os.path.exists(tmp_mp3):
                    try: os.remove(tmp_mp3)
                    except OSError: pass

        try:
            # Safely execute async coroutine regardless of thread or active loop state
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(lambda: asyncio.run(_run())).result(timeout=120)
            else:
                try:
                    asyncio.run(_run())
                except RuntimeError:
                    new_loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(_run())
                    finally:
                        try:
                            new_loop.run_until_complete(new_loop.shutdown_asyncgens())
                        except Exception:
                            pass
                        new_loop.close()
                        asyncio.set_event_loop(None)
            return timed_segments
        except Exception as e:
            raise RuntimeError(f"Edge-TTS failed: {e}")

    def _synth_elevenlabs(self, text, out_path, cfg, speed, chunk_limit, cb) -> List[dict]:
        from core.elevenlabs_client import synthesize_elevenlabs_audio
        import config.settings as CFG_mod
        user_cfg = CFG_mod.load()
        smart_pacing = user_cfg.get("smart_pacing", True)
        model_id = user_cfg.get("elevenlabs_model_id", "eleven_multilingual_v2")
        v_id = cfg["id"]
        v_name = cfg.get("name", v_id)

        log.step(f"ElevenLabs Synthesis — voice='{v_name}' (ID: {v_id}) model='{model_id}' speed={speed}x")

        # Sentence-based chunking allows seamless key rotation across small chunks if credits run out
        effective_limit = min(chunk_limit, 280) if chunk_limit > 0 else 280
        chunks = chunk_text(text, limit=effective_limit, smart_pacing=smart_pacing)
        if not chunks:
            clean = text.strip()
            chunks = [clean] if clean else []

        if not chunks:
            return []

        tmps = []
        timed_segments = []
        pauses = []
        cur_t = 0.0
        try:
            for i, chunk in enumerate(chunks, 1):
                clean_chunk = chunk.strip()
                if not clean_chunk:
                    continue
                if cb:
                    cb(f"Synthesizing chunk {i}/{len(chunks)} with ElevenLabs…")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                tmps.append(tmp)

                seg_dur = synthesize_elevenlabs_audio(
                    text=clean_chunk,
                    voice_id=v_id,
                    out_wav_path=tmp,
                    model_id=model_id,
                    speed=speed,
                    cb=cb
                )

                timed_segments.append({
                    "text": clean_chunk,
                    "start": cur_t,
                    "end": cur_t + seg_dur
                })
                cur_t += seg_dur

                if i < len(chunks):
                    p_dur = calculate_chunk_pause(chunk) if smart_pacing else 0.0
                    pauses.append(p_dur)
                    cur_t += p_dur

            if cb:
                cb(f"Stitching {len(tmps)} audio chunks…")
            concat_wavs(tmps, out_path, pauses=pauses)
            log.info(f"ElevenLabs synthesis completed: stitched {len(tmps)} chunks into {out_path}")
            return timed_segments
        finally:
            for p in tmps:
                try: os.remove(p)
                except OSError: pass
