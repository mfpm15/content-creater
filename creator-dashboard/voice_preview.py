"""Bounded test narration before rendering a full faceless video.

Uses the same Edge-TTS worker and voice settings as production. It never
silently falls back to music or a paid service.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import tempfile
import threading

from runtime_config import resolve_python
from security import render_environment
import speech_settings
import voice_quality


ROOT = Path(__file__).resolve().parent
VOICE_ENV = ROOT / "apps" / "lemo-opuscar"
WORKER = ROOT / "speech_worker.py"
GATE = threading.BoundedSemaphore(1)
MAX_TEXT = 170
MAX_WAV_BYTES = 3 * 1024 * 1024


def preview(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) - {"language", "text"}:
        raise ValueError("Permintaan preview suara tidak valid")
    text = payload.get("text")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT or any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ValueError("Contoh narasi wajib 1–170 karakter")
    if not GATE.acquire(blocking=False):
        raise ValueError("Tes suara lain masih berlangsung")
    try:
        voice = speech_settings.build(payload.get("language", "id"), "tts", False)
        python = resolve_python(VOICE_ENV)
        if not python.is_file():
            raise RuntimeError("Runtime Edge-TTS belum diinstal, jalankan setup-core.bat")
        with tempfile.TemporaryDirectory(prefix="voice-studio-preview-") as dirname:
            target = Path(dirname)
            source = target / "voice-lines.json"
            source.write_text(json.dumps([{"id": "scene-1", "text": text.strip(), "voice": voice["voice"],
                                          "rate": voice["rate"]}], ensure_ascii=False), "utf-8")
            try:
                result = subprocess.run(
                    [str(python), str(WORKER), str(source), str(target / "voice")],
                    capture_output=True, timeout=90, env=render_environment(), check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Provider TTS tidak menjawab; periksa koneksi sebelum render") from exc
            if result.returncode:
                raise RuntimeError("Sintesis Edge-TTS gagal; periksa jaringan/proxy lalu coba lagi")
            output = target / "voice" / "scene-1.wav"
            if not output.is_file() or output.stat().st_size > MAX_WAV_BYTES:
                raise RuntimeError("Provider menghasilkan audio yang tidak valid")
            metrics = voice_quality.require_audible(output)
            return {
                "voice": voice["voice"],
                "duration": metrics["duration"],
                "audioBase64": base64.b64encode(output.read_bytes()).decode("ascii"),
                "mime": "audio/wav",
                "note": "Suara preview bukan jaminan semua scene atau durasi render akan berhasil.",
            }
    finally:
        GATE.release()
