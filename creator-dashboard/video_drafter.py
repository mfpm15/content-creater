"""Video Drafter: AI Video Generator Studio.
Input prompt / topik -> Naskah & Visual disusun oleh LLM (9Router) -> HTML HyperFrames + GSAP -> MP4 Video.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
VIDEOS_DIR = ROOT / "output" / "videos"
HYPERFRAMES_APP_DIR = ROOT / "apps" / "hyperframes"

LLM_URL = os.getenv("VIDEO_LLM_BASE_URL", "http://localhost:20128/v1").rstrip("/")
LLM_MODEL = os.getenv("VIDEO_LLM_MODEL", "ag/gemini-3.8-flash-high")
LLM_KEY = os.getenv("VIDEO_LLM_API_KEY", "9router-local")
LLM_TIMEOUT = int(os.getenv("VIDEO_LLM_TIMEOUT", "120"))

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")

STYLES = {
    "tech_keynote": {
        "id": "tech_keynote",
        "name": "Tech Keynote (Dark SaaS)",
        "description": "Desain modern profesional, tipografi elegan, gradien halus, gerakan mulus.",
        "bg": "radial-gradient(circle at 75% 25%, #312e81, #0f172a 60%, #030712)",
        "accent": "#6366f1",
        "accent_text": "#c7d2fe",
    },
    "neon_cyberpunk": {
        "id": "neon_cyberpunk",
        "name": "Neon Cyberpunk (Futuristic)",
        "description": "Warna neon menyala, kartu hologram, aksen cyan-magenta dinamis.",
        "bg": "linear-gradient(135deg, #090014 0%, #17072b 50%, #020617 100%)",
        "accent": "#ec4899",
        "accent_text": "#38bdf8",
    },
    "vibrant_social": {
        "id": "vibrant_social",
        "name": "Vibrant Reel (TikTok / Shorts)",
        "description": "Warna kontras tinggi, pop spring bounce, animasi teks cepat siap FYP.",
        "bg": "linear-gradient(160deg, #ff0055 0%, #7928ca 50%, #000000 100%)",
        "accent": "#facc15",
        "accent_text": "#ffffff",
    },
    "minimal_swiss": {
        "id": "minimal_swiss",
        "name": "Swiss Typographic (Minimalist)",
        "description": "Grid presisi, tata letak monokrom tegas, satu warna aksen sinyal.",
        "bg": "#0c0d0e",
        "accent": "#ff3b30",
        "accent_text": "#f5f5f7",
    },
    "watercolor_art": {
        "id": "watercolor_art",
        "name": "Opuscar Cinematic (Artistic)",
        "description": "Sentuhan artistik berkelas, bayangan lembut, tipografi berjiwa film.",
        "bg": "radial-gradient(circle at 50% 40%, #1e293b, #0f172a 70%, #020617)",
        "accent": "#38bdf8",
        "accent_text": "#f8fafc",
    },
}

ASPECT_RATIOS = {
    "9:16": {"width": 1080, "height": 1920, "label": "9:16 Vertikal (Shorts / Reels / TikTok)"},
    "16:9": {"width": 1920, "height": 1080, "label": "16:9 Horizontal (YouTube / Layar)"},
    "1:1": {"width": 1080, "height": 1080, "label": "1:1 Persegi (Feed Instagram / Sosmed)"},
}

DURATIONS = [5, 10, 15]

JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}


def options() -> dict:
    return {
        "styles": list(STYLES.values()),
        "aspects": [{"id": k, **v} for k, v in ASPECT_RATIOS.items()],
        "durations": DURATIONS,
        "defaultStyle": "tech_keynote",
        "defaultAspect": "9:16",
        "defaultDuration": 5,
    }


def list_videos() -> list[dict]:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for directory in sorted(VIDEOS_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0, reverse=True):
        if not directory.is_dir():
            continue
        meta_file = directory / "metadata.json"
        video_file = directory / "video.mp4"
        if meta_file.is_file() and video_file.is_file():
            try:
                with meta_file.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["hasVideo"] = True
                meta["videoSize"] = video_file.stat().st_size
                meta["videoUrl"] = f"/api/videos/{directory.name}/video.mp4"
                meta["htmlUrl"] = f"/api/videos/{directory.name}/index.html"
                results.append(meta)
            except Exception:
                continue
    return results


def get_video(slug: str) -> dict:
    target_dir = VIDEOS_DIR / slug
    if not target_dir.is_dir():
        raise FileNotFoundError(f"Video {slug} tidak ditemukan")
    meta_file = target_dir / "metadata.json"
    video_file = target_dir / "video.mp4"
    if not meta_file.is_file() or not video_file.is_file():
        raise FileNotFoundError(f"File video atau metadata {slug} belum lengkap")
    with meta_file.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["videoSize"] = video_file.stat().st_size
    meta["videoUrl"] = f"/api/videos/{slug}/video.mp4"
    meta["htmlUrl"] = f"/api/videos/{slug}/index.html"
    return meta


def read_video_file(slug: str, filename: str) -> tuple[bytes, str]:
    target_dir = VIDEOS_DIR / slug
    file_path = target_dir / filename
    if not file_path.is_file() or not str(file_path.resolve()).startswith(str(VIDEOS_DIR.resolve())):
        raise FileNotFoundError(f"File {filename} tidak ditemukan")
    ext = file_path.suffix.lower()
    content_type = "video/mp4" if ext == ".mp4" else ("text/html; charset=utf-8" if ext in (".html", ".htm") else "application/octet-stream")
    return file_path.read_bytes(), content_type


def job_status(job_id: str) -> dict:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id} tidak ditemukan")
        return dict(job)


def start_job(payload: dict) -> dict:
    topic = str(payload.get("topic") or "").strip()
    if not topic:
        raise ValueError("Topik video wajib diisi")

    style_id = str(payload.get("style") or "tech_keynote").strip()
    if style_id not in STYLES:
        style_id = "tech_keynote"

    aspect_id = str(payload.get("aspect") or "9:16").strip()
    if aspect_id not in ASPECT_RATIOS:
        aspect_id = "9:16"

    try:
        duration = int(payload.get("duration") or 5)
    except (ValueError, TypeError):
        duration = 5
    if duration not in DURATIONS:
        duration = 5

    script_notes = str(payload.get("script") or "").strip()

    job_id = uuid.uuid4().hex
    job = {
        "jobId": job_id,
        "topic": topic,
        "style": style_id,
        "aspect": aspect_id,
        "duration": duration,
        "script": script_notes,
        "status": "queued",
        "step": "Menyiapkan antrian generator",
        "progress": 5,
        "error": None,
        "video": None,
        "startedAt": time.time(),
        "finishedAt": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    worker = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    worker.start()
    return {"jobId": job_id, "status": "queued"}


def _call_9router(prompt: str) -> str:
    url = f"{LLM_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "CreatorDashboard-VideoStudio/1.0",
    }
    body = {
        "model": LLM_MODEL,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Kamu sutradara motion graphics dan video designer profesional. "
                    "Buat naskah video pendek yang menarik, ringkas, dan visual. "
                    "Balas HANYA satu objek JSON valid tanpa markdown tambahan."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    choices = res.get("choices") or []
    if not choices:
        raise RuntimeError("LLM tidak mengembalikan jawaban")
    content = choices[0].get("message", {}).get("content", "")
    return content


def _clean_json(raw: str) -> dict:
    trimmed = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", trimmed, re.IGNORECASE)
    if match and match.group(1):
        trimmed = match.group(1).strip()
    first_brace = trimmed.find("{")
    last_brace = trimmed.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        trimmed = trimmed[first_brace : last_brace + 1]
    return json.loads(trimmed)


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", cleaned)[:50].strip("-")
    if not slug:
        slug = f"video-{int(time.time())}"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


def _generate_html_composition(
    topic: str,
    script_data: dict,
    style_info: dict,
    aspect_info: dict,
    duration: int,
) -> str:
    width = aspect_info["width"]
    height = aspect_info["height"]
    is_portrait = height > width

    title_size = "64px" if is_portrait else "76px"
    body_size = "30px" if is_portrait else "34px"
    badge_size = "20px" if is_portrait else "22px"

    badge_text = script_data.get("badge") or "HIGHLIGHT"
    headline = script_data.get("headline") or topic
    subline = script_data.get("subline") or "Solusi Praktis & Cepat"
    callout = script_data.get("callout") or "Tonton Sampai Akhir"

    bg_style = style_info["bg"]
    accent = style_info["accent"]
    accent_text = style_info["accent_text"]

    d1 = round(duration * 0.1, 2)
    d2 = round(duration * 0.25, 2)
    d3 = round(duration * 0.45, 2)
    d4 = round(duration * 0.70, 2)

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>{headline}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #000000;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      color: #ffffff;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      overflow: hidden;
    }}
    #stage {{
      width: {width}px;
      height: {height}px;
      background: {bg_style};
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      padding: {'60px' if is_portrait else '80px'};
      text-align: center;
    }}
    .glow-circle {{
      position: absolute;
      width: {'700px' if is_portrait else '900px'};
      height: {'700px' if is_portrait else '900px'};
      border-radius: 50%;
      background: {accent};
      filter: blur(140px);
      opacity: 0.25;
      z-index: 0;
    }}
    #badge {{
      background: {accent};
      color: #ffffff;
      padding: 12px 32px;
      border-radius: 9999px;
      font-size: {badge_size};
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      margin-bottom: 28px;
      z-index: 1;
    }}
    #title {{
      font-size: {title_size};
      font-weight: 900;
      line-height: 1.15;
      margin: 0 0 24px;
      max-width: 90%;
      letter-spacing: -0.02em;
      color: #ffffff;
      text-shadow: 0 4px 20px rgba(0,0,0,0.6);
      z-index: 1;
    }}
    #desc {{
      font-size: {body_size};
      line-height: 1.5;
      color: {accent_text};
      max-width: 82%;
      margin: 0 0 36px;
      z-index: 1;
    }}
    #callout-card {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.18);
      backdrop-filter: blur(20px);
      border-radius: 20px;
      padding: 18px 40px;
      font-size: {badge_size};
      font-weight: 700;
      color: #ffffff;
      box-shadow: 0 20px 40px rgba(0,0,0,0.4);
      z-index: 1;
    }}
    .progress-bar {{
      position: absolute;
      bottom: 0;
      left: 0;
      height: 8px;
      background: {accent};
      width: 0%;
      z-index: 10;
    }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="video" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}">
    <div class="glow-circle"></div>
    <div id="badge" class="clip" data-start="{d1}" data-duration="{round(duration - d1, 2)}" data-track-index="0">{badge_text}</div>
    <h1 id="title" class="clip" data-start="{d2}" data-duration="{round(duration - d2, 2)}" data-track-index="1">{headline}</h1>
    <p id="desc" class="clip" data-start="{d3}" data-duration="{round(duration - d3, 2)}" data-track-index="2">{subline}</p>
    <div id="callout-card" class="clip" data-start="{d4}" data-duration="{round(duration - d4, 2)}" data-track-index="3">{callout}</div>
    <div class="progress-bar clip" data-start="0" data-duration="{duration}" data-track-index="4"></div>

    <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.from("#badge", {{ opacity: 0, scale: 0.6, y: -20, duration: 0.6, ease: "back.out(2)" }}, {d1});
      tl.from("#title", {{ opacity: 0, y: 50, duration: 0.8, ease: "power3.out" }}, {d2});
      tl.from("#desc", {{ opacity: 0, y: 35, duration: 0.8, ease: "power2.out" }}, {d3});
      tl.from("#callout-card", {{ opacity: 0, scale: 0.85, y: 25, duration: 0.6, ease: "back.out(1.5)" }}, {d4});
      tl.to(".progress-bar", {{ width: "100%", duration: {duration}, ease: "none" }}, 0);

      window.__timelines = window.__timelines || {{}};
      window.__timelines.video = tl;
    </script>
  </div>
</body>
</html>
"""


def _update_job(job_id: str, updates: dict):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)


def _run_job(job_id: str):
    with JOBS_LOCK:
        job = dict(JOBS[job_id])

    topic = job["topic"]
    style_key = job["style"]
    aspect_key = job["aspect"]
    duration = job["duration"]
    script_prompt = job.get("script") or ""

    style_info = STYLES.get(style_key, STYLES["tech_keynote"])
    aspect_info = ASPECT_RATIOS.get(aspect_key, ASPECT_RATIOS["9:16"])
    slug = _slugify(topic)
    target_dir = VIDEOS_DIR / slug

    try:
        # Tahap 1: Tanya LLM 9Router
        _update_job(job_id, {"status": "generating", "step": "1/3: Menyusun konsep & copywriting via 9Router AI...", "progress": 20})
        prompt = (
            f"Buat copywriting untuk video motion graphics pendek {duration} detik.\n"
            f"Topik: {topic}\n"
            f"Catatan tambahan / poin naskah: {script_prompt or 'Buat poin paling tajam dan memikat'}\n"
            f"Format response JSON WAJIB berisi:\n"
            "{\n"
            '  "badge": "label badge pendek huruf kapital (maksimal 3 kata)",\n'
            '  "headline": "headline utama video yang memikat (maksimal 8 kata)",\n'
            '  "subline": "kalimat penjelasan atau poin kunci (maksimal 15 kata)",\n'
            '  "callout": "ajakan aksi atau simpulan akhir (maksimal 6 kata)"\n'
            "}"
        )
        llm_raw = _call_9router(prompt)
        script_data = _clean_json(llm_raw)

        # Tahap 2: Rakit HTML HyperFrames
        _update_job(job_id, {"step": "2/3: Merangkai timeline animasi GSAP & visual...", "progress": 50})
        target_dir.mkdir(parents=True, exist_ok=True)
        html_code = _generate_html_composition(topic, script_data, style_info, aspect_info, duration)
        html_file = target_dir / "index.html"
        html_file.write_text(html_code, encoding="utf-8")

        # Tahap 3: Render ke MP4 via HyperFrames
        _update_job(job_id, {"step": "3/3: Merender video MP4 dengan HyperFrames & Chromium...", "progress": 70})
        output_mp4 = target_dir / "video.mp4"

        env = os.environ.copy()
        extra_paths = [
            str(ROOT / "bin"),
            r"C:\Users\Terrestrial\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin",
        ]
        if os.name == "nt":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                    upath, _ = winreg.QueryValueEx(k, "Path")
                    extra_paths.extend([p.strip() for p in upath.split(";") if p.strip()])
            except Exception:
                pass
        full_path = os.pathsep.join([p for p in extra_paths if p]) + os.pathsep + env.get("PATH", "")
        env["PATH"] = full_path
        env["Path"] = full_path

        cmd = [
            "node",
            str((HYPERFRAMES_APP_DIR / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs").resolve()),
            "render",
            "-o",
            str(output_mp4.resolve()),
            "--fps",
            "30",
        ]

        proc = subprocess.run(cmd, cwd=str(target_dir), env=env, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not output_mp4.is_file():
            err_msg = proc.stderr or proc.stdout or "Render HyperFrames gagal menghasilkan MP4"
            raise RuntimeError(f"Gagal render video: {err_msg[:400]}")

        # Metadata simpan
        meta = {
            "slug": slug,
            "topic": topic,
            "style": style_info,
            "aspect": aspect_info,
            "duration": duration,
            "scriptData": script_data,
            "createdAt": time.time(),
            "formattedTime": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (target_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        _update_job(
            job_id,
            {
                "status": "succeeded",
                "step": "Video berhasil dibuat!",
                "progress": 100,
                "finishedAt": time.time(),
                "video": {
                    "slug": slug,
                    "title": script_data.get("headline", topic),
                    "videoUrl": f"/api/videos/{slug}/video.mp4",
                    "htmlUrl": f"/api/videos/{slug}/index.html",
                    "size": output_mp4.stat().st_size,
                    "duration": duration,
                },
            },
        )

    except Exception as exc:
        _update_job(
            job_id,
            {
                "status": "failed",
                "step": f"Gagal: {exc}",
                "progress": 100,
                "error": str(exc),
                "finishedAt": time.time(),
            },
        )
