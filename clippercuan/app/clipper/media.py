"""Pembungkus ffmpeg: probe, ekstrak audio, ambil frame, energi audio."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import FFMPEG

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], cwd: str | Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [FFMPEG, "-hide_banner", "-nostdin", *args]
    p = subprocess.run(cmd, cwd=cwd, capture_output=capture, creationflags=_NO_WINDOW)
    if p.returncode != 0:
        tail = (p.stderr or b"").decode("utf-8", "replace")[-2500:]
        raise FFmpegError(f"ffmpeg gagal ({p.returncode}):\n{tail}")
    return p


@dataclass
class Probe:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    hdr: bool = False


def probe(path: str | Path) -> Probe:
    """Baca info video dari stderr `ffmpeg -i` (tidak butuh ffprobe)."""
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, creationflags=_NO_WINDOW)
    err = p.stderr.decode("utf-8", "replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise FFmpegError(f"Bukan file video yang valid: {path}\n{err[-800:]}")
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    v = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5})", err)
    if not v:
        raise FFmpegError("File tidak punya stream video.")
    f = re.search(r"(\d+(?:\.\d+)?) fps", err)
    w, h = int(v[1]), int(v[2])
    rot = re.search(r"rotate\s*:\s*(-?\d+)|rotation of (-?\d+)", err)
    if rot and abs(int(rot[1] or rot[2])) in (90, 270):
        w, h = h, w
    vline = next((ln for ln in err.splitlines() if "Video:" in ln), "")
    hdr = any(k in vline for k in ("smpte2084", "arib-std-b67", "bt2020"))
    return Probe(dur, w, h, float(f[1]) if f else 30.0, "Audio:" in err, hdr)


_ENCODERS: list[str] | None = None
_HW_BROKEN: set[str] = set()
HW_ORDER = ("h264_nvenc", "h264_qsv", "h264_videotoolbox", "h264_amf")


def encoders() -> list[str]:
    global _ENCODERS
    if _ENCODERS is None:
        try:
            p = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20, creationflags=_NO_WINDOW)
            _ENCODERS = [e for e in HW_ORDER if f" {e} " in p.stdout]
        except (OSError, subprocess.TimeoutExpired):
            _ENCODERS = []
    return [e for e in _ENCODERS if e not in _HW_BROKEN]


def video_codec_args(height: int, encoder: str = "auto", fast: bool = False) -> tuple[str, list[str]]:
    """Argumen encode H.264 berkualitas tinggi. Hardware (NVIDIA/Intel/Apple/AMD) bila ada, cadangan libx264."""
    hw = encoders()[0] if encoder == "auto" and encoders() else (encoder if encoder in encoders() else None)
    br = "45M" if height >= 3000 else "24M" if height >= 2000 else "14M"   # untuk encoder berbasis bitrate
    if hw == "h264_nvenc":
        return hw, ["-c:v", hw, "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-maxrate", br, "-bufsize", br, "-profile:v", "high"]
    if hw == "h264_qsv":
        return hw, ["-c:v", hw, "-preset", "slower", "-global_quality", "20", "-profile:v", "high"]
    if hw == "h264_videotoolbox":
        return hw, ["-c:v", hw, "-b:v", br, "-maxrate", br, "-profile:v", "high", "-allow_sw", "1"]
    if hw == "h264_amf":
        return hw, ["-c:v", hw, "-quality", "quality", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20", "-profile:v", "high"]
    preset = "veryfast" if fast else ("faster" if height >= 3000 else "medium")
    return "libx264", ["-c:v", "libx264", "-preset", preset, "-crf", "18", "-profile:v", "high", "-x264-params", "aq-mode=3"]


_FILTERS: str | None = None


def has_filter(name: str) -> bool:
    global _FILTERS
    if _FILTERS is None:
        try:
            _FILTERS = subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20,
                                      creationflags=_NO_WINDOW).stdout
        except (OSError, subprocess.TimeoutExpired):
            _FILTERS = ""
    return f" {name} " in _FILTERS


def mark_hw_broken(name: str) -> None:
    _HW_BROKEN.add(name)


def extract_audio(src: Path, dst: Path) -> Path:
    run(["-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])
    return dst


def audio_energy(wav: Path, hop: float = 0.5) -> np.ndarray:
    """RMS per `hop` detik, dinormalisasi 0..1 — dipakai untuk skor momen."""
    import wave

    with wave.open(str(wav), "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = int(16000 * hop)
    if raw.size < n:
        return np.zeros(1)
    frames = raw[: raw.size // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    lo, hi = np.percentile(rms, 5), np.percentile(rms, 98)
    return np.clip((rms - lo) / max(hi - lo, 1e-6), 0, 1)


def grab_frame(src: Path, t: float, dst: Path, width: int = 960) -> Path:
    run(["-y", "-ss", f"{max(t, 0):.3f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)])
    return dst


def visual_activity(src: Path, duration: float, hop: float = 0.5) -> np.ndarray | None:
    """Aktivitas visual 0..1 per `hop` detik dari selisih antar-keyframe (cepat: hanya keyframe yang di-decode).

    Menangkap pergantian scene, gerak besar, dan aksi gameplay. None bila gagal / terlalu sedikit keyframe.
    """
    w, h = 64, 36
    try:
        p = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-skip_frame", "nokey", "-i", str(src), "-an",
                            "-vf", f"scale={w}:{h},format=gray,showinfo", "-fps_mode", "passthrough", "-f", "rawvideo", "-"],
                           capture_output=True, creationflags=_NO_WINDOW, timeout=max(120, duration / 4))
    except (OSError, subprocess.TimeoutExpired):
        return None
    ts = [float(x) for x in re.findall(r"pts_time:(-?[\d.]+)", p.stderr.decode("utf-8", "replace"))]
    n = min(len(p.stdout) // (w * h), len(ts))
    if n < 3:
        return None
    frames = np.frombuffer(p.stdout[: n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)
    diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))           # perubahan antar keyframe
    mid = (np.array(ts[1:n]) + np.array(ts[: n - 1])) / 2
    grid = np.arange(0, max(duration, hop), hop) + hop / 2
    vals = np.interp(grid, mid, diff)
    lo, hi = np.percentile(vals, 5), np.percentile(vals, 95)
    return np.clip((vals - lo) / max(hi - lo, 1e-6), 0, 1)
