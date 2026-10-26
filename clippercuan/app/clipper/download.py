"""Ambil video sumber: link (YouTube dan situs lain yang didukung yt-dlp) atau file lokal."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from .config import FFMPEG, UPLOADS_DIR


def is_url(s: str) -> bool:
    return s.strip().lower().startswith(("http://", "https://"))


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


def fetch(source: str, out_dir: Path, progress: Callable[[float, str], None] = lambda p, m: None) -> tuple[Path, str]:
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

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress(d.get("downloaded_bytes", 0) / total, f"Mengunduh {d.get('_percent_str', '').strip()}")

    opts = {
        "outtmpl": str(out_dir / "source.%(ext)s"),
        # maks 1080p, gabung jadi mp4 agar cepat dipotong
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "retries": 5,
        "fragment_retries": 5,
    }
    opts.update(_youtube_js_opts())
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source.strip(), download=True)
    files = sorted(out_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
    files = [f for f in files if f.suffix not in (".part", ".ytdl")]
    if not files:
        raise RuntimeError("Unduhan selesai tetapi file video tidak ditemukan.")
    return files[0], info.get("title") or "Video"


# ------------------------------------------------------------------ mode hemat disk (lite)
VIDEO_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
_STREAMS: dict[str, tuple[float, dict]] = {}


def _ydl_opts(**extra) -> dict:
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "ffmpeg_location": FFMPEG,
            "retries": 5, **_youtube_js_opts(), **extra}


def resolve_streams(source: str, max_age: float = 1800) -> dict:
    """URL stream langsung (video + audio) tanpa mengunduh. Di-cache karena URL YouTube berlaku beberapa jam."""
    hit = _STREAMS.get(source)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    import yt_dlp

    with yt_dlp.YoutubeDL(_ydl_opts(format=VIDEO_FORMAT)) as ydl:
        info = ydl.extract_info(source.strip(), download=False)
    fmts = info.get("requested_formats") or [info]
    video = next((f for f in fmts if f.get("vcodec") not in (None, "none")), fmts[0])
    audio = next((f for f in fmts if f is not video and f.get("acodec") not in (None, "none")), None)
    if audio is None and video.get("acodec") in (None, "none"):
        audio = None
    pick = lambda f: {"url": f["url"], "headers": f.get("http_headers") or info.get("http_headers") or {}}  # noqa: E731
    data = {"title": info.get("title") or "Video", "duration": float(info.get("duration") or 0),
            "width": int(video.get("width") or info.get("width") or 1920), "height": int(video.get("height") or info.get("height") or 1080),
            "fps": float(video.get("fps") or info.get("fps") or 30), "video": pick(video), "audio": pick(audio) if audio else None}
    _STREAMS[source] = (time.time(), data)
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


def fetch_audio(source: str, out_dir: Path, progress: Callable[[float, str], None] = lambda p, m: None) -> tuple[Path, dict]:
    """Mode hemat: hanya audio (untuk transkripsi & energi) + metadata video. Video penuh tidak disimpan."""
    progress(0.1, "Membaca info video (mode hemat)…")
    meta = resolve_streams(source)
    src = meta["audio"] or meta["video"]
    out = out_dir / "audio-source.m4a"
    progress(0.4, "Mengambil audio saja (mode hemat disk)…")
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(src), "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "64k", str(out)]
    p = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        _STREAMS.pop(source, None)
        raise RuntimeError("Gagal mengambil audio: " + p.stderr.decode("utf-8", "replace")[-600:])
    progress(1.0, "Audio siap")
    return out, meta


def fetch_segment(source: str, start: float, end: float, dst: Path) -> Path:
    """Unduh & potong presisi hanya rentang [start, end] (re-encode cepat) untuk dirender."""
    meta = resolve_streams(source)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(meta["video"], start, end)]
    if meta["audio"]:
        cmd += [*_input(meta["audio"], start, end), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(dst)]
    p = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        _STREAMS.pop(source, None)  # URL kedaluwarsa → ambil ulang di percobaan berikutnya
        raise RuntimeError("Gagal mengambil potongan video: " + p.stderr.decode("utf-8", "replace")[-600:])
    return dst


def grab_remote_frame(source: str, t: float, dst: Path, width: int = 640) -> Path:
    meta = resolve_streams(source)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *_input(meta["video"], max(t, 0)),
           "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)]
    subprocess.run(cmd, capture_output=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return dst
