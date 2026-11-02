"""Ambil video sumber: link (YouTube dan situs lain yang didukung yt-dlp) atau file lokal."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .config import FFMPEG, UPLOADS_DIR


def is_url(s: str) -> bool:
    return s.strip().lower().startswith(("http://", "https://"))


def source_identity(source: str, info: dict | None = None) -> dict:
    """Identitas publik ringkas untuk atribusi di video, tanpa menampilkan URL panjang."""
    info = info or {}
    if not is_url(source):
        name = Path(source.replace('\\', '/')).stem.split("__", 1)[-1] or "file lokal"
        return {"platform": "File lokal", "creator": "", "label": f"Sumber: {name}"[:80]}
    host = (urlparse(source.strip()).hostname or "sumber video").lower().removeprefix("www.")
    platform = str(info.get("extractor_key") or info.get("extractor") or "").strip()
    if not platform:
        platform = {"youtu.be": "YouTube", "youtube.com": "YouTube", "tiktok.com": "TikTok",
                    "instagram.com": "Instagram", "facebook.com": "Facebook"}.get(host, host)
    creator = str(info.get("channel") or info.get("uploader") or info.get("creator") or "").strip()
    creator = " ".join(creator.split())[:48]
    label = f"Sumber: {platform}" + (f" · {creator}" if creator else "")
    return {"platform": platform[:32], "creator": creator, "label": label[:80], "host": host}


def _youtube_js_opts() -> dict:
    """YouTube kini butuh runtime JavaScript (deno/node/bun/quickjs) + yt-dlp-ejs untuk memecahkan tantangan player."""
    runtimes = {name: {} for name in ("deno", "node", "bun", "quickjs") if shutil.which(name)}
    opts: dict = {"remote_components": ["ejs:github"]}  # solver diunduh sekali bila paket yt-dlp-ejs tidak terpasang
    if runtimes:
        opts["js_runtimes"] = runtimes
    browser = _cookies_browser()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    return opts


def _cookies_browser() -> str:
    import os

    try:
        from .llm import load_settings

        value = os.environ.get("CLIPPER_COOKIES_BROWSER") or load_settings()["download"].get("cookies_browser", "")
    except Exception:  # noqa: BLE001
        value = os.environ.get("CLIPPER_COOKIES_BROWSER", "")
    return value if value in {"chrome", "edge", "firefox", "brave", "safari", "chromium", "opera", "vivaldi"} else ""


def fetch(source: str, out_dir: Path, progress: Callable[[float, str], None] = lambda p, m: None,
          max_h: int = 1440) -> tuple[Path, str]:
    """Kembalikan (path video, judul sumber)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not is_url(source):
        src = Path(source).expanduser()
        if not src.is_file():
            prev = [f for f in out_dir.glob("source.*") if f.suffix not in (".part", ".ytdl")]
            if prev:  # ulangi proyek: file unggahan sudah dipindah ke folder proyek
                return prev[0], src.stem.split("__", 1)[-1]
            raise FileNotFoundError(f"File tidak ditemukan: {src}")
        name = src.stem.split("__", 1)[-1]  # unggahan: "<id>__<nama asli>"
        if src.parent.resolve() != UPLOADS_DIR.resolve():
            return src.resolve(), name  # file milik pengguna dipakai langsung: tidak diduplikasi ke folder proyek
        dst = out_dir / ("source" + src.suffix.lower())
        if src.resolve() != dst.resolve():
            progress(0.5, "Memindahkan file…")
            shutil.move(str(src), dst)  # unggahan: pindah, bukan salin (hemat disk)
        return dst, name

    import yt_dlp

    progress(0.01, "Membaca metadata dan menyiapkan unduhan video penuh…")

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = int(d.get("downloaded_bytes") or 0)
            fraction = downloaded / total if total else 0.01
            size = f"{downloaded / 1048576:.1f} MB"
            progress(max(0.01, min(fraction, .99)), f"Mengunduh video penuh · {size} {d.get('_percent_str', '').strip()}".strip())
        elif d.get("status") == "finished":
            progress(0.99, "Unduhan selesai, menggabungkan video dan audio…")

    opts = {
        "outtmpl": str(out_dir / "source.%(ext)s"),
        # resolusi terbaik ≤ max_h (portrait tajam butuh sumber > 1080p); digabung ke mkv agar VP9/AV1 + Opus aman
        "format": video_format(max_h), "format_sort": FORMAT_SORT,
        "merge_output_format": "mkv",
        "ffmpeg_location": FFMPEG,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        # Jangan biarkan koneksi CDN yang mati menggantungkan worker tanpa batas.
        # File .part tetap dipakai yt-dlp untuk melanjutkan retry berikutnya.
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 10), "fragment": lambda n: min(2 ** n, 10)},
        "concurrent_fragment_downloads": 3,
    }
    opts.update(_youtube_js_opts())
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source.strip(), download=True)
    import json
    (out_dir / "source-info.json").write_text(json.dumps(source_identity(source, info), ensure_ascii=False), "utf-8")
    files = sorted(out_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
    files = [f for f in files if f.suffix not in (".part", ".ytdl")]
    if not files:
        raise RuntimeError("Unduhan selesai tetapi file video tidak ditemukan.")
    write_chapters(out_dir, info.get("chapters"))
    return files[0], info.get("title") or "Video"


def write_chapters(out_dir: Path, chapters) -> None:
    """Simpan chapter dari sumber (batas topik bersih) ke chapters.json; kosong bila sumber tak punya."""
    import json

    rows = [{"s": float(c["start_time"]), "e": float(c["end_time"]), "title": str(c.get("title") or "")}
            for c in chapters or [] if c.get("start_time") is not None and c.get("end_time") is not None]
    f = Path(out_dir) / "chapters.json"
    if rows:
        f.write_text(json.dumps(rows, ensure_ascii=False), "utf-8")
    else:
        f.unlink(missing_ok=True)


# ------------------------------------------------------------------ mode hemat disk (lite)
def video_format(max_h: int) -> str:
    """Resolusi terbaik ≤ max_h, utamakan SDR (HDR butuh tonemap). 4K YouTube hanya tersedia sebagai VP9/AV1."""
    return (f"bv*[height<={max_h}][dynamic_range=SDR]+ba/bv*[height<={max_h}]+ba/"
            f"b[height<={max_h}]/b")


FORMAT_SORT = ["res", "fps", "vcodec:vp9", "acodec:opus"]   # resolusi dulu; VP9 lebih ringan di-decode daripada AV1


def source_height(cfg: dict | None, lite: bool) -> int:
    raw = str(((cfg or {}).get("quality") or {}).get("source", "auto"))
    if raw.isdigit():
        return int(raw)
    out = int(str(((cfg or {}).get("quality") or {}).get("output", "1080")) or 1080)
    return 2160 if lite or out >= 1440 else 1440


VIDEO_FORMAT = video_format(2160)
_STREAMS: dict[str, tuple[float, dict]] = {}


def _ydl_opts(**extra) -> dict:
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "ffmpeg_location": FFMPEG,
            "socket_timeout": 20, "retries": 3, "fragment_retries": 3,
            **_youtube_js_opts(), **extra}


def resolve_streams(source: str, max_age: float = 1800, max_h: int = 2160) -> dict:
    """URL stream langsung (video + audio) tanpa mengunduh. Di-cache karena URL YouTube berlaku beberapa jam."""
    key = f"{max_h}|{source}"
    hit = _STREAMS.get(key)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    import yt_dlp

    with yt_dlp.YoutubeDL(_ydl_opts(format=video_format(max_h), format_sort=FORMAT_SORT)) as ydl:
        info = ydl.extract_info(source.strip(), download=False)
    fmts = info.get("requested_formats") or [info]
    video = next((f for f in fmts if f.get("vcodec") not in (None, "none")), fmts[0])
    audio = next((f for f in fmts if f is not video and f.get("acodec") not in (None, "none")), None)
    if audio is None and video.get("acodec") in (None, "none"):
        audio = None
    pick = lambda f: {"url": f["url"], "headers": f.get("http_headers") or info.get("http_headers") or {}}  # noqa: E731
    data = {"title": info.get("title") or "Video", "duration": float(info.get("duration") or 0), "chapters": info.get("chapters"),
            "width": int(video.get("width") or info.get("width") or 1920), "height": int(video.get("height") or info.get("height") or 1080),
            "fps": float(video.get("fps") or info.get("fps") or 30), "video": pick(video), "audio": pick(audio) if audio else None,
            "source_identity": source_identity(source, info)}
    _STREAMS[key] = (time.time(), data)
    return data


def _input(stream: dict, start: float | None = None, end: float | None = None) -> list[str]:
    args = []
    hdr = "".join(f"{k}: {v}\r\n" for k, v in (stream.get("headers") or {}).items())
    if hdr and stream["url"].lower().startswith("http"):
        args += ["-headers", hdr]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    if end is not None:
        args += ["-to", f"{end:.3f}"]
    return args + ["-i", stream["url"]]


def fetch_audio(source: str, out_dir: Path, progress: Callable[[float, str], None] = lambda p, m: None,
                max_h: int = 2160) -> tuple[Path, dict]:
    """Mode hemat: hanya audio (untuk transkripsi & energi) + metadata video. Video penuh tidak disimpan."""
    progress(0.1, "Membaca info video (mode hemat)…")
    meta = resolve_streams(source, max_h=max_h)
    src = meta["audio"] or meta["video"]
    out = out_dir / "audio-source.m4a"
    progress(0.4, "Mengambil audio saja (mode hemat disk)…")
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(src), "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "64k", str(out)]
    p = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        _STREAMS.clear()
        raise RuntimeError("Gagal mengambil audio: " + p.stderr.decode("utf-8", "replace")[-600:])
    progress(1.0, "Audio siap")
    return out, meta


def fetch_segment(source: str, start: float, end: float, dst: Path, max_h: int = 2160) -> Path:
    """Unduh & potong presisi hanya rentang [start, end] untuk dirender (encode antara hampir lossless)."""
    meta = resolve_streams(source, max_h=max_h)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(meta["video"], start, end)]
    if meta["audio"]:
        cmd += [*_input(meta["audio"], start, end), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(dst)]
    p = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        _STREAMS.clear()  # URL kedaluwarsa → ambil ulang di percobaan berikutnya
        raise RuntimeError("Gagal mengambil potongan video: " + p.stderr.decode("utf-8", "replace")[-600:])
    return dst


def grab_remote_frame(source: str, t: float, dst: Path, width: int = 640, max_h: int = 2160) -> Path:
    meta = resolve_streams(source, max_h=max_h)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(meta["video"], max(t, 0)),
           "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)]
    subprocess.run(cmd, capture_output=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return dst
