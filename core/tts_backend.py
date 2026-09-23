"""
core/tts_backend.py – Kokoro-82M TTS engine (CPU, Python 3.10–3.13)

Kokoro is a state-of-the-art neural TTS model (Apache 2.0 licence) that
produces near-broadcast-quality speech in multiple voices and accents.
Audio quality is dramatically better than Silero for social media content.

Backend: kokoro-onnx  (ONNX Runtime, CPU-only, no GPU required)
Sample rate: 24 000 Hz mono WAV
"""

import os
import wave
import tempfile
from typing import Callable, List, Optional

import numpy as np
import soundfile as sf

from config.settings import (
    VOICE_CATALOGUE, MODEL_FILE, VOICES_FILE, SAMPLE_RATE, CHUNK_CHAR_LIMIT
)
from core.logger import log


# ─────────────────────────────────────────────────────────────────────────────
#  Text chunking  (sentence-aligned, respects Kokoro's phoneme window)
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT) -> List[str]:
    """
    Split text into sentence-aligned chunks each ≤ *limit* characters.
    Kokoro handles up to ~510 phonemes per call; 300 chars is a safe proxy.
    """
    import re
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Split at sentence boundaries first, then paragraph breaks
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
                    # Break oversized single words/tokens (e.g. URLs, base64) into sub-limit slices
                    if cur:
                        chunks.append(cur)
                        cur = ""
                    for i in range(0, len(word), limit):
                        sub = word[i:i+limit]
                        chunks.append(sub)
                else:
                    cand = (cur + " " + word).strip()
                    if len(cand) <= limit:
                        cur = cand
                    else:
                        if cur:
                            chunks.append(cur)
                        cur = word
        else:
            cand = (cur + " " + sent).strip()
            if len(cand) <= limit:
                cur = cand
            else:
                if cur:
                    chunks.append(cur)
                cur = sent
    if cur:
        chunks.append(cur)
    return chunks or [text]


# ─────────────────────────────────────────────────────────────────────────────
#  WAV merge (stdlib wave – no extra deps)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
#  Engine
# ─────────────────────────────────────────────────────────────────────────────

class TTSEngine:
    """
    Kokoro-82M ONNX engine.  Single instance, loaded lazily.
    Not thread-safe – designed to be owned by the worker thread.
    """

    def __init__(self):
        self._kokoro = None

    def _load(self):
        if self._kokoro is not None:
            return
        if not MODEL_FILE.exists() or not VOICES_FILE.exists():
            raise RuntimeError(
                "Kokoro model files not found. "
                "Please restart the app so the startup dialog can download them."
            )
        log.step(f"Loading Kokoro ONNX model from {MODEL_FILE}…")
        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(str(MODEL_FILE), str(VOICES_FILE))
        voices = self._kokoro.get_voices()
        log.info(f"Kokoro loaded — {len(voices)} voices available")

    def synthesize(
        self,
        text: str,
        out_path: str,
        voice: str,
        speed: float = 1.0,
        chunk_limit: int = CHUNK_CHAR_LIMIT,
        cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Synthesise *text* → WAV at *out_path*. Long texts are auto-chunked."""
        cfg  = VOICE_CATALOGUE[voice]
        v_id = cfg["id"]
        lang = cfg["lang"]

        log.step(
            f"Synthesis — voice='{v_id}' lang='{lang}' speed={speed}x "
            f"chars={len(text)} → '{os.path.basename(out_path)}'"
        )

        if cb: cb("Loading model…")
        self._load()

        # Verify voice exists in the loaded model
        available = self._kokoro.get_voices()
        if v_id not in available:
            log.warn(
                f"Voice '{v_id}' not in model. Available: {available[:5]}…  "
                f"Falling back to first available voice."
            )
            v_id = available[0]

        chunks = chunk_text(text, limit=chunk_limit)
        log.info(f"Text split into {len(chunks)} chunk(s) (limit={chunk_limit})")

        if len(chunks) == 1:
            if cb: cb("Synthesising…")
            self._synth_one(chunks[0], out_path, v_id, lang, speed)
            log.info(f"Done → {os.path.basename(out_path)}")
            return

        tmps: List[str] = []
        try:
            for i, chunk in enumerate(chunks, 1):
                msg = f"Chunk {i} / {len(chunks)}"
                if cb: cb(msg)
                log.debug(f"  {msg}  ({len(chunk)} chars)")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp = tf.name
                self._synth_one(chunk, tmp, v_id, lang, speed)
                tmps.append(tmp)
            if cb: cb("Merging audio…")
            log.info(f"Merging {len(tmps)} chunks → {os.path.basename(out_path)}")
            concat_wavs(tmps, out_path)
            log.info(f"Done → {os.path.basename(out_path)}")
        finally:
            for p in tmps:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError: pass

    def _synth_one(self, text: str, out: str,
                   voice_id: str, lang: str, speed: float) -> None:
        samples, sr = self._kokoro.create(
            text, voice=voice_id, speed=speed, lang=lang
        )
        # samples is float32 numpy array, sr=24000
        sf.write(out, samples, sr, subtype="PCM_16")
