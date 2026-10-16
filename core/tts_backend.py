"""
core/tts_backend.py – Multi-Backend TTS Engine (Kokoro, Piper, Edge-TTS)
Supports English (Kokoro), Multilingual Offline (Piper), and Online (Edge-TTS).
"""

import os
import wave
import asyncio
import tempfile
from typing import Callable, List, Optional

import numpy as np
import soundfile as sf

from config.settings import (
    VOICE_CATALOGUE, MODEL_FILE, VOICES_FILE, SAMPLE_RATE, CHUNK_CHAR_LIMIT, resolve_voice
)
from core.logger import log
from core.model_manager import ensure_piper_voice_downloaded


def generate_srt(text: str, duration: float, output_path: str) -> None:
    """
    Generate an SRT subtitle file from transcript text and audio duration.
    Guarantees every subtitle chunk has a duration of AT MOST 3.0 seconds,
    with a natural rhythm variation between 2.0 and 3.0 seconds (no chunks >= 3.001s or 4s).
    """
    try:
        import math
        import re
        from pathlib import Path
        srt_file = Path(output_path).parent / "transcript.srt"

        if duration <= 0 or not text or not text.strip():
            srt_file.write_text("", encoding="utf-8")
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
    except Exception as e:
        from core.logger import log
        log.error(f"Failed to generate SRT file: {e}")
        from core.logger import log
        log.error(f"Failed to generate SRT file: {e}")


def preprocess_text_pacing(text: str) -> str:
    """Enhance text punctuation and spacing for more natural cadence and breath pauses."""
    import re
    # Add subtle pauses after key punctuation marks
    text = re.sub(r'([;:])\s*', r'\1 ', text)
    # Ensure em-dashes have spaces for pause naturalness
    text = re.sub(r'—', ' — ', text)
    # Normalize multiple ellipses to a uniform pause marker
    text = re.sub(r'\.{3,}', '...', text)
    return text.strip()


def enhance_audio_signal(samples: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    Apply mastering filter chain to raw TTS output:
    1. High-pass filter (cut sub-80Hz rumble)
    2. Subtle presence boost / high-frequency smoothing
    3. Peak normalization to -1.0 dBFS
    """
    if len(samples) == 0:
        return samples

    # Ensure float32 [-1, 1]
    samples = samples.astype(np.float32)

    try:
        from scipy.signal import butter, sosfilt
        # High-pass filter at 75 Hz (remove low-end thumps/rumble)
        sos_hp = butter(2, 75, 'hp', fs=sr, output='sos')
        samples = sosfilt(sos_hp, samples)

        # Gentle high-shelf / presence filter at 3500 Hz
        sos_lp = butter(1, 12000, 'lp', fs=sr, output='sos')
        samples = sosfilt(sos_lp, samples)
    except ImportError:
        # Fallback if scipy is unavailable: basic DC offset removal
        samples = samples - np.mean(samples)

    # Peak normalization to -1.0 dBFS (0.8912)
    max_val = np.max(np.abs(samples))
    if max_val > 1e-5:
        target_peak = 0.8912
        samples = samples * (target_peak / max_val)

    return samples


def master_audio(samples: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    Apply audio post-processing (DSP mastering chain) to elevate TTS realism:
    1. High-Pass Filter (removes rumble below 80Hz)
    2. Peak & Loudness Normalization
    3. Soft High-Frequency Smoothing
    """
    if len(samples) == 0:
        return samples

    audio = samples.astype(np.float32)

    # 1. High-Pass Filter (removes low-end DC offset & subsonic rumble below 80Hz)
    try:
        from scipy.signal import butter, sosfilt
        sos = butter(2, 80, 'hp', fs=sr, output='sos')
        audio = sosfilt(sos, audio)
    except Exception:
        # Fallback simple DC removal if scipy filter isn't active
        audio = audio - np.mean(audio)

    # 2. Dynamic Normalization (-1.0 dB target peak)
    max_val = np.max(np.abs(audio))
    if max_val > 1e-5:
        target_peak = 0.90  # ~ -0.9 dB peak
        audio = (audio / max_val) * target_peak

    return audio


def preprocess_text_for_pacing(text: str) -> str:
    """
    Enhance natural pauses, breathing room, and punctuation cadence.
    """
    import re
    # Add subtle spacing after em-dashes and ellipses for better pause rendering
    text = re.sub(r"(\.{3,}|…)", r"\1 ", text)
    text = re.sub(r"—", " — ", text)
    text = re.sub(r" {2,}", " ", text)
    return text


def chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT, smart_pacing: bool = True) -> List[str]:
    """Split text into sentence-aligned chunks each ≤ *limit* characters."""
    import re
    if smart_pacing:
        text = preprocess_text_for_pacing(text)

    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    parts = re.split(r"(?<=[.!?])\s+|\n\n", text)
    sentences = [p.strip() for p in parts if p.strip()]

    chunks: List[str] = []
    cur = ""

    for sent in sentences:
        if len(sent) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            for word in sent.split():
                if len(word) > limit:
                    if cur:
                        chunks.append(cur)
                        cur = ""
                    for i in range(0, len(word), limit):
                        chunks.append(word[i:i+limit])
                else:
                    cand = (cur + " " + word).strip()
                    if len(cand) <= limit:
                        cur = cand
                    else:
                        if cur: chunks.append(cur)
                        cur = word
        else:
            cand = (cur + " " + sent).strip()
            if len(cand) <= limit:
                cur = cand
            else:
                if cur: chunks.append(cur)
                cur = sent
    if cur:
        chunks.append(cur)
    return chunks or [text]


def concat_wavs(paths: List[str], out: str) -> None:
    if not paths:
        return
    params = None
    frames = []
    for p in paths:
        with wave.open(p, "rb") as wf:
            if not params:
                params = wf.getparams()
            frames.append(wf.readframes(wf.getnframes()))
    if not params:
        return
    with wave.open(out, "wb") as wf:
        wf.setparams(params)
        for f in frames:
            wf.writeframes(f)


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
    ) -> None:
        resolved_voice = resolve_voice(voice)
        cfg = VOICE_CATALOGUE.get(resolved_voice, next(iter(VOICE_CATALOGUE.values())))
        backend = cfg.get("backend", "kokoro")

        if backend == "kokoro":
            self._synth_kokoro(text, out_path, cfg, speed, chunk_limit, cb)
        elif backend == "piper":
            self._synth_piper(text, out_path, cfg, speed, chunk_limit, cb)
        elif backend == "edgetts":
            self._synth_edgetts(text, out_path, cfg, speed, cb)
        else:
            raise ValueError(f"Unknown TTS backend: {backend}")

    def _synth_kokoro(self, text, out_path, cfg, speed, chunk_limit, cb):
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
            samples, sr = self._kokoro.create(chunks[0], voice=v_id, speed=speed, lang=lang)
            if do_mastering:
                samples = master_audio(samples, sr)
            sf.write(out_path, samples, sr, format='WAV', subtype="PCM_16")
            return

        tmps = []
        try:
            for i, chunk in enumerate(chunks, 1):
                if cb: cb(f"Chunk {i}/{len(chunks)}")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                samples, sr = self._kokoro.create(chunk, voice=v_id, speed=speed, lang=lang)
                if do_mastering:
                    samples = master_audio(samples, sr)
                sf.write(tmp, samples, sr, format='WAV', subtype="PCM_16")
                tmps.append(tmp)
            if cb: cb("Merging audio…")
            concat_wavs(tmps, out_path)
        finally:
            for p in tmps:
                try: os.remove(p)
                except OSError: pass

    def _synth_piper(self, text, out_path, cfg, speed, chunk_limit, cb):
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

        chunks = chunk_text(text, limit=chunk_limit)
        tmps = []
        try:
            for i, chunk in enumerate(chunks, 1):
                if cb: cb(f"Synthesising chunk {i}/{len(chunks)}")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                with wave.open(tmp, "wb") as wav_file:
                    voice_inst.synthesize(chunk, wav_file, length_scale=1.0/speed)
                tmps.append(tmp)
            if cb: cb("Merging audio…")
            concat_wavs(tmps, out_path)
        finally:
            for p in tmps:
                try: os.remove(p)
                except OSError: pass

    def _synth_edgetts(self, text, out_path, cfg, speed, cb):
        v_id = cfg["id"]
        log.step(f"Edge-TTS Synthesis — voice='{v_id}' speed={speed}x")
        if cb: cb("Connecting to Edge-TTS…")

        import edge_tts

        # Edge rate format: "+0%" or "+50%" or "-20%"
        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"

        async def _run():
            communicate = edge_tts.Communicate(text, v_id, rate=rate_str)
            # Temporary mp3 file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_mp3 = tf.name

            try:
                await communicate.save(tmp_mp3)
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
        except Exception as e:
            raise RuntimeError(f"Edge-TTS failed: {e}")
