"""Lightweight PCM sanity check before treating an online TTS response as dubbing.

This tests that a returned WAV actually contains audible samples. It cannot
establish that the words are correct; that still requires playback/review.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import math
import sys
import wave


def require_audible(path: Path) -> dict:
    """Reject zero-length, truncated and effectively silent WAV narration.

    Scan short samples at several positions to avoid reading an entire long
    production into RAM. Fail closed for formats the current worker does not
    produce, rather than accidentally reporting success for unreadable output.
    """
    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            count = wav.getnframes()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            if not (rate >= 8000 and count >= rate // 8 and channels in (1, 2) and width == 2):
                raise ValueError("WAV TTS tidak valid atau terlalu pendek")
            samples = min(count, max(2000, rate // 3))
            positions = sorted(set([0, max(0, count // 4), max(0, count // 2), max(0, count * 3 // 4), max(0, count - samples)]))
            observed_peak = 0
            total_square = 0
            total_samples = 0
            for position in positions:
                wav.setpos(min(position, count - samples))
                raw = wav.readframes(samples)
                if len(raw) < samples * channels * width:
                    raise ValueError("WAV TTS terpotong")
                values = array("h")
                values.frombytes(raw)
                if sys.byteorder != "little":
                    values.byteswap()
                for value in values:
                    observed_peak = max(observed_peak, abs(value))
                    total_square += value * value
                total_samples += len(values)
            rms = math.sqrt(total_square / max(1, total_samples))
            # About -45 dBFS RMS and -35 dBFS peak. This is not a
            # perceptual speech-quality score, only a silence/corruption gate.
            if observed_peak < 600 or rms < 180:
                raise ValueError("Hasil TTS senyap atau terlalu pelan; periksa penyedia suara")
            return {"duration": count / rate, "peak_pcm16": observed_peak, "rms_pcm16": round(rms, 1)}
    except (OSError, EOFError, wave.Error) as exc:
        raise ValueError("WAV hasil TTS tidak dapat dibaca") from exc
