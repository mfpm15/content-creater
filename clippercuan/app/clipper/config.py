"""Lokasi data, binary ffmpeg, dan nilai default."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "ClipperCuan"
PKG_DIR = Path(__file__).resolve().parent
WEB_DIR = PKG_DIR / "web"
FONTS_DIR = PKG_DIR / "fonts"

DATA_DIR = Path(os.environ.get("CLIPPER_HOME", Path.home() / APP_NAME)).expanduser()
PROJECTS_DIR = DATA_DIR / "projects"
MODELS_DIR = DATA_DIR / "models"
UPLOADS_DIR = DATA_DIR / "uploads"
for d in (PROJECTS_DIR, MODELS_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _find_ffmpeg() -> str:
    env = os.environ.get("CLIPPER_FFMPEG")
    if env:
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # ffmpeg bawaan paket pip, jadi pengguna tidak perlu memasang manual
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        sys.exit("ffmpeg tidak ditemukan. Jalankan installer (start) ulang atau pasang ffmpeg.")


FFMPEG = _find_ffmpeg()

# Default pipeline — semua bisa diubah dari UI per proyek.
DEFAULTS: dict = {
    "recipe": "recommended",     # default aman: Clean Large, satu spoken-caption stabil
    "caption_layers": 1,          # invariant: satu layer transcript aktif per timestamp
    "source_has_burned_captions": "unknown",  # unknown | yes | no; heuristik hanya warning
    "min_score": 45,             # render otomatis melewati kandidat di bawah skor ini (minimal 1 klip tetap dibuat)
    "storage": "full",           # full | lite (link: hanya audio + potongan klip yang diunduh)
    "content_profile": "auto",  # auto | podcast | tech_review | mobile_legends
    "candidate_count": 15,       # kandidat dibuat & diranking (seperti "Detected clips")
    "auto_render": False,        # kandidat harus dipilih sebelum batch render
    "diversity": 0.30,           # bobot MMR untuk variasi semantik/scene/speaker
    "max_overlap": 0.35,
    "language": "auto",          # auto | id | en | ms | ar | ja | ko | es | ...
    "translate_en": False,       # caption diterjemahkan ke Inggris (Whisper translate)
    "model": "small",            # tiny | base | small | medium | large-v3
    "transcriber": "auto",       # auto | youtube | api | local  (auto: YouTube → API cloud → Whisper lokal)
    "clip_count": "auto",        # jumlah render otomatis; "auto" = ±1 per 3 menit video, 3–10 (≥30 menit = 10)
    "duration_preset": "auto",  # auto | 15-25 | 25-40 | 40-60 | custom
    "min_sec": 15,
    "max_sec": 60,
    "layout": "portrait",        # portrait | square | blur | split | landscape
    "smart_crop": True,          # ikuti wajah
    "cut_silence": False,        # potong jeda hening (jump cut)
    "silence_gap": 0.55,         # detik jeda minimum yang dipotong
    "split": {                   # area dalam pecahan (0..1) dari frame sumber
        "face": [0.70, 0.62, 0.30, 0.38],   # x, y, w, h  (default: facecam pojok kanan bawah)
        "game": [0.0, 0.0, 1.0, 1.0],
        "face_ratio": 0.4,       # porsi tinggi frame output untuk facecam (atas)
    },
    "caption": {
        "enabled": True,
        "role": "spoken-caption",
        "preset": "clean-large",
        "template_id": "clean-large",
        "size_level": "large",
        "style": "clean",        # box | wbw | karaoke | clean | keyword
        "font": "Barlow Condensed",
        "size": 84,
        "outline": 4,
        "shadow": 0,
        "color": "#FFFFFF",
        "highlight": "#FFD166",
        "uppercase": False,
        "words_per_line": 5,
        "max_lines": 2,
        "line_height": 1.12,
        "position": "bottom",    # bottom | middle | top
        "safe_area": 0.18,
        "max_chars": 30,
        "animation": "none",     # pop | none
        "box": False,            # kotak berwarna mengikuti kata aktif (bisa dipadu gaya apa pun)
        "effect": "none",        # none | glow
        "glow_color": "",
        "y_pct": 74,             # posisi vertikal bebas 8..92 (% tinggi frame)
        "accent_font": "Barlow Condensed",  # font kata kunci; mode color mempertahankan font utama
        "accent_mode": "color",        # color | font
        "accent_scale": 108,            # pembesaran halus 100..115 agar layout tetap stabil
    },
    "title": {
        "enabled": False,
        "role": "hook",
        "preset": "clean",       # bar | outline | neon | clean | duo
        "duration": 3,            # hook wajib terbatas; 0 tidak lagi menjadi default
        "size": 58,
        "y_pct": 12,
        "accent": "#3DE0A0",     # preset duo: warna baris punchline
        "glow": "#C6FF3D",
    },
    "emoji": {"enabled": False, "size": 1.0},
    "progress_bar": {"enabled": False, "color": "#FFC933", "height": 12, "position": "bottom"},
    "cta": {"enabled": False, "text": "Follow untuk part berikutnya!", "duration": 3},
    "music": {"enabled": False, "file": "", "volume": 0.15, "duck": True},
    "audio": {"normalize": True, "target_lufs": -16.0, "true_peak": -1.5},
    "quality": {
        "output": "1080",        # 1080 | 1440 | 2160 (4K) — sisi pendek video hasil
        "source": "auto",        # tinggi maks sumber: auto (hemat: 2160, penuh: 1440) | 1080 | 1440 | 2160
        "encoder": "auto",       # auto (GPU NVIDIA/Intel/Apple/AMD bila ada, cadangan CPU) | cpu
        "sharpen": True,         # penajaman ringan bila sumber harus diperbesar
    },
    "composition": {"subtle_punch_in": True, "max_zoom": 1.035, "scene_aware": True},
    "watermark": {
        "enabled": False,
        "text": "@namakamu",
        "image": "",             # path gambar PNG (opsional)
        "position": "br",        # tl | tr | bl | br | c
        "opacity": 0.8,
        "size": 42,
    },
}

SIZES = {
    "portrait": (1080, 1920),
    "split": (1080, 1920),
    "blur": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}


def deep_merge(base: dict, extra: dict | None) -> dict:
    out = {k: (deep_merge(v, {}) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out
