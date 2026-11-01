"""Cek hasil render terhadap aturan platform (TikTok / YouTube Shorts / Instagram Reels).

Ide dari ffmpeg-skill: jangan lapor "selesai" sebelum file hasil dibuka dan diukur.
`evaluate()` murni (mudah dites); `check()` mengukur file dengan ffmpeg lalu memanggil `evaluate()`.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import media

FPS_MAX = 60  # ffmpeg-skill: fps_max 60 untuk semua platform ini; 23,98 fps (sinema) sah, bukan "patah"
# Angka disalin dari tabel PLATFORMS di ffmpeg-skill (scripts/_platforms.py), bukan dari dokumentasi resmi platform.
# ponytail: ubah di sini bila platform berubah; upgrade: baca dari satu berkas JSON bila platform bertambah.
PLATFORMS = {
    "tiktok": {"label": "TikTok", "max_sec": 600, "min_height": 1080, "lufs": -14.0, "aspects": ("9:16", "1:1")},
    "shorts": {"label": "YouTube Shorts", "max_sec": 180, "min_height": 1080, "lufs": -14.0, "aspects": ("9:16", "1:1")},
    "reels": {"label": "Instagram Reels", "max_sec": 90, "min_height": 1080, "lufs": -14.0, "aspects": ("9:16", "4:5", "1:1")},
}
ALIASES = {"youtube": "shorts", "youtube-shorts": "shorts", "yt": "shorts", "ig": "reels", "instagram": "reels"}
LUFS_TOLERANCE = 2.0
ASPECT_TOLERANCE = 0.02


def _ratio(text: str) -> float:
    a, b = text.split(":")
    return int(a) / int(b)


def platform_id(name: str) -> str:
    key = (name or "").strip().lower()
    key = ALIASES.get(key, key)
    if key not in PLATFORMS:
        raise ValueError(f"Platform tidak dikenal: {name!r}. Pilihan: {', '.join(PLATFORMS)}")
    return key


def _issue(level: str, code: str, msg: str) -> dict:
    return {"level": level, "code": code, "msg": msg}


def evaluate(info: dict, platform: str) -> dict:
    """info: duration, width, height, fps, has_audio, lufs (None bila tak terukur)."""
    pid = platform_id(platform)
    spec = PLATFORMS[pid]
    issues = []
    w, h, dur = int(info.get("width") or 0), int(info.get("height") or 0), float(info.get("duration") or 0)
    if w <= 0 or h <= 0:
        issues.append(_issue("error", "no-video", "Ukuran video tidak terbaca."))
    elif not any(abs(w / h - _ratio(a)) <= _ratio(a) * ASPECT_TOLERANCE for a in spec["aspects"]):
        issues.append(_issue("error", "aspect", f"Rasio {w}x{h} bukan {' / '.join(spec['aspects'])}; {spec['label']} memotong atau memberi bingkai hitam."))
    if w > 0 and h > 0 and min(w, h) < spec["min_height"]:
        issues.append(_issue("warn", "resolution", f"Sisi pendek {min(w, h)}px di bawah {spec['min_height']}px; hasil bisa terlihat lembek."))
    if dur > spec["max_sec"]:
        issues.append(_issue("error", "duration", f"Durasi {dur:.0f}s melebihi batas {spec['label']} ({spec['max_sec']}s)."))
    if dur <= 0:
        issues.append(_issue("error", "duration", "Durasi nol."))
    if float(info.get("fps") or 0) > FPS_MAX + 0.01:
        issues.append(_issue("error", "fps", f"FPS {info.get('fps')} melebihi {FPS_MAX}; platform menurunkannya sendiri."))
    if not info.get("has_audio"):
        issues.append(_issue("error", "no-audio", "Tidak ada audio."))
    else:
        lufs = info.get("lufs")
        if lufs is None:
            issues.append(_issue("warn", "loudness-unmeasured", "Loudness tidak terukur."))
        elif abs(lufs - spec["lufs"]) > LUFS_TOLERANCE:
            issues.append(_issue("warn", "loudness", f"Loudness {lufs:.1f} LUFS; target {spec['lufs']:.0f} ±{LUFS_TOLERANCE:.0f}."))
    return {"platform": pid, "label": spec["label"], "ok": not any(i["level"] == "error" for i in issues),
            "issues": issues, "measured": {k: info.get(k) for k in ("duration", "width", "height", "fps", "has_audio", "lufs")}}


def measure_lufs(path: Path) -> float | None:
    """Integrated loudness lewat filter ebur128; None bila gagal atau senyap total."""
    try:
        p = media.run(["-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"])
    except media.FFmpegError:
        return None
    err = (p.stderr or b"").decode("utf-8", "replace")
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    m = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", tail)
    return float(m[1]) if m else None


def check(path: str | Path, platform: str) -> dict:
    platform_id(platform)  # gagal cepat sebelum menjalankan ffmpeg
    pr = media.probe(path)
    lufs = measure_lufs(Path(path)) if pr.has_audio else None
    return evaluate({"duration": pr.duration, "width": pr.width, "height": pr.height, "fps": pr.fps,
                     "has_audio": pr.has_audio, "lufs": lufs}, platform)


def check_all(path: str | Path) -> dict:
    """Satu kali ukur, evaluasi ke semua platform."""
    pr = media.probe(path)
    lufs = measure_lufs(Path(path)) if pr.has_audio else None
    info = {"duration": pr.duration, "width": pr.width, "height": pr.height, "fps": pr.fps, "has_audio": pr.has_audio, "lufs": lufs}
    return {pid: evaluate(info, pid) for pid in PLATFORMS}
