"""Server lokal (hanya 127.0.0.1) yang melayani UI dan API."""
from __future__ import annotations

from .security import redact

import base64
import hmac
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import BinaryIO

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from contextlib import asynccontextmanager

from . import __version__, asr, automation, effects, llm, media, profiles, project
from .captions import FONT_PRESETS
from .config import DATA_DIR, DEFAULTS, FONTS_DIR, UPLOADS_DIR, WEB_DIR

def _configure_file_logging() -> logging.Logger:
    """Simpan log aplikasi dan Uvicorn ke berkas berputar di direktori data Clipper."""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "clipper.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger = logging.getLogger("clipper")
    if not any(isinstance(item, RotatingFileHandler) for item in logger.handlers):
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").addHandler(handler)
    return logger


_log = _configure_file_logging()
_MODEL_CHECK: dict = {"checked_at": None, "available": [], "missing": [], "error": None}


def _check_model_catalog() -> dict:
    """Bandingkan model pada rantai fallback dengan katalog 9Router tanpa menjalankan inferensi."""
    global _MODEL_CHECK
    configured = list(dict.fromkeys(llm.chain_for("posts") + llm.chain_for("moments")))
    try:
        available = llm.list_models(llm.cfg())
        available_set = set(available)
        _MODEL_CHECK = {
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "available": [model for model in configured if model in available_set],
            "missing": [model for model in configured if model not in available_set],
            "catalog_size": len(available),
            "error": None,
        }
        _log.info("9Router model check: %s tersedia, %s hilang", len(_MODEL_CHECK["available"]), len(_MODEL_CHECK["missing"]))
    except Exception as exc:  # noqa: BLE001
        _MODEL_CHECK = {
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "available": [], "missing": configured, "error": redact(str(exc))[:300],
        }
        _log.warning("9Router model check gagal: %s", exc)
    return _MODEL_CHECK


def _model_monitor() -> None:
    interval = max(300, int(os.environ.get("CLIPPER_MODEL_CHECK_INTERVAL", "1800")))
    while True:
        _check_model_catalog()
        time.sleep(interval)


@asynccontextmanager
async def lifespan(_app):
    project.start_worker()
    threading.Thread(target=_model_monitor, name="clipper-model-monitor", daemon=True).start()
    _log.info("ClipperCuan dimulai; data=%s", DATA_DIR)
    yield


app = FastAPI(title="ClipperCuan", version=__version__, lifespan=lifespan)

TOKEN = os.environ.get("CLIPPER_TOKEN", "").strip()
MAX_UPLOAD_BYTES = int(os.environ.get("CLIPPER_MAX_UPLOAD_MB", "4096")) * 1024 * 1024
MAX_MUSIC_BYTES = int(os.environ.get("CLIPPER_MAX_MUSIC_MB", "512")) * 1024 * 1024


def _authorized(header: str, token: str) -> bool:
    """Validasi Bearer atau Basic auth tanpa menerima Basic yang tidak punya pemisah username/password."""
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() == "bearer":
        return bool(credentials) and hmac.compare_digest(credentials.strip(), token)
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
        _, separator, password = decoded.partition(":")
        return bool(separator) and hmac.compare_digest(password, token)
    except (ValueError, UnicodeDecodeError):
        return False


def _copy_limited(source: BinaryIO, destination: Path, limit: int) -> None:
    """Salin stream dengan batas ukuran dan hapus file parsial bila batas terlampaui."""
    written = 0
    try:
        with destination.open("wb") as out:
            while chunk := source.read(4 << 20):
                written += len(chunk)
                if written > limit:
                    raise ValueError("File terlalu besar")
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"} | {
    h.strip().lower() for h in os.environ.get("CLIPPER_ALLOWED_HOSTS", "").split(",") if h.strip()}


def _host_only(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):
        return value.split("]")[0] + "]"
    return value.split(":")[0]


def _local_request_ok(host: str, origin: str, method: str) -> bool:
    """Mode lokal tanpa token: tolak DNS-rebinding (Host asing) dan POST/PUT/DELETE lintas-situs (Origin asing)."""
    if _host_only(host) not in LOCAL_HOSTS:
        return False
    if method in {"POST", "PUT", "PATCH", "DELETE"} and origin and origin != "null":
        from urllib.parse import urlparse

        if (urlparse(origin).netloc or "").lower() != host.strip().lower():
            return False
    return True


@app.middleware("http")
async def auth(request: Request, call_next):
    """Mode server/cloud: wajib token (Bearer untuk agent, Basic auth untuk browser). Lokal tanpa token: hanya Host/Origin lokal."""
    if TOKEN:
        if not _authorized(request.headers.get("authorization", ""), TOKEN):
            return Response("Butuh login ClipperCuan", status_code=401, headers={"WWW-Authenticate": 'Basic realm="ClipperCuan"'})
    elif not _local_request_ok(request.headers.get("host", ""), request.headers.get("origin", ""), request.method):
        return Response("Permintaan ditolak: Host/Origin bukan lokal", status_code=403)
    # Basic credentials may be attached automatically by a browser. Reject
    # cross-origin mutations even when authentication itself succeeded.
    origin = request.headers.get("origin")
    if origin and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(origin)
            same_origin = parsed.scheme == request.url.scheme and parsed.netloc.lower() == request.headers.get("host", "").lower()
        except ValueError:
            same_origin = False
        if not same_origin:
            return Response("Permintaan lintas-origin ditolak", status_code=403)
    return await call_next(request)


class NewProject(BaseModel):
    source: str
    settings: dict = {}


class ClipEdit(BaseModel):
    changes: dict
    rerender: bool = True


class Settings(BaseModel):
    settings: dict


class CandidateSelection(BaseModel):
    ids: list[str] = []


class CandidateAction(BaseModel):
    action: str
    value: bool = True


class ProjectSettings(BaseModel):
    settings: dict
    rerender: bool = False


class CaptionWorkspaceSave(BaseModel):
    revision: int | None = None
    data: dict


class CaptionWorkspaceAction(BaseModel):
    action: str
    payload: dict = {}


class ProfilePreview(BaseModel):
    profile: str = "auto"
    classification_confidence: float = 0.0
    evidence: list[str] = []


def _get(pid: str) -> dict:
    try:
        return project.load(pid)
    except KeyError:
        raise HTTPException(404, "Proyek tidak ditemukan")


@app.get("/api/health")
def health():
    """Health ringan untuk launcher/dashboard; status akurat tanpa membuka credential."""
    c = llm.cfg()
    configured = llm.explicitly_configured(c)
    enabled = bool(c.get("enabled") and configured)
    return {"ok": True, "service": "clippercuan", "version": __version__,
            "llm": {"configured": configured, "enabled": enabled,
                    "mode": "9router" if enabled else "local_fallback",
                    "base_url": c.get("base_url"), "model": c.get("model_moments"),
                    "credential_configured": bool(c.get("api_key"))}}


@app.get("/api/info")
def info():
    return {"version": __version__, "data_dir": str(DATA_DIR), "defaults": DEFAULTS, "fonts": list(FONT_PRESETS),
            "profiles": profiles.public_registry(), "inbox_dir": str(automation.INBOX_DIR)}


@app.get("/api/export-profiles")
def export_profiles():
    from . import delivery

    return {"source": delivery.SPEC["source"], "verified_official": delivery.SPEC["verified_official"],
            "profiles": {name: {key: spec[key] for key in ("label", "safe", "max_sec", "lufs", "aspects")}
                         for name, spec in delivery.PLATFORMS.items()}}


@app.get("/api/profiles")
def content_profiles():
    return {"source_of_truth": "backend", "profiles": profiles.public_registry(),
            "aliases": profiles.ALIASES, "fallback": profiles.resolve("general")}


@app.post("/api/profiles/preview")
def preview_profile(body: ProfilePreview):
    classification = {"profile": body.profile, "confidence": body.classification_confidence,
                      "evidence": body.evidence}
    resolved = profiles.resolve_selection(body.profile, classification)
    return {"resolved": resolved, "confidence": round(body.classification_confidence, 3),
            "reasons": [resolved["reason"], *body.evidence]}


@app.get("/api/recipes")
def recipes():
    from .recipes import PROFILE_DEFAULT, public

    return {"recipes": public(), "profile_default": PROFILE_DEFAULT}


@app.get("/api/projects")
def projects():
    return project.list_projects()


@app.post("/api/projects")
def new_project(body: NewProject):
    src = body.source.strip()
    if not src:
        raise HTTPException(400, "Isi link video atau pilih file")
    if src.startswith("upload:"):
        f = UPLOADS_DIR / src[7:]
        if not f.is_file() or f.parent != UPLOADS_DIR:
            raise HTTPException(400, "File unggahan tidak ditemukan")
        src = str(f)
    elif not src.lower().startswith(("http://", "https://")):
        f = Path(src).expanduser()
        if not f.is_file():
            raise HTTPException(400, "Link harus diawali http(s):// atau path file yang ada")
        if TOKEN and not f.resolve().is_relative_to(DATA_DIR.resolve()):
            raise HTTPException(400, "Mode server: file harus diunggah atau ditaruh di folder inbox/data ClipperCuan")
    return project.create(src, body.settings)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "video.mp4").suffix.lower()[:6] or ".mp4"
    if ext not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Format file tidak didukung")
    stem = re.sub(r"[^\w\- ]+", "", Path(file.filename or "video").stem, flags=re.UNICODE).strip()[:60] or "video"
    name = f"{uuid.uuid4().hex[:12]}__{stem}{ext}"
    dst = UPLOADS_DIR / name
    try:
        _copy_limited(file.file, dst, MAX_UPLOAD_BYTES)
    except ValueError:
        raise HTTPException(413, f"File video melebihi batas {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    return {"id": "upload:" + name, "path": str(dst), "name": file.filename}


@app.get("/api/music")
def music():
    return effects.list_music()


@app.post("/api/music")
async def upload_music(file: UploadFile = File(...)):
    ext = Path(file.filename or "musik.mp3").suffix.lower()
    if ext not in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}:
        raise HTTPException(400, "Format musik tidak didukung (mp3, m4a, wav, ogg, flac)")
    stem = re.sub(r"[^\w\- ]+", "", Path(file.filename or "musik").stem, flags=re.UNICODE).strip()[:60] or "musik"
    dst = effects.MUSIC_DIR / f"{stem}{ext}"
    n = 2
    while dst.exists():
        dst = effects.MUSIC_DIR / f"{stem} ({n}){ext}"
        n += 1
    try:
        _copy_limited(file.file, dst, MAX_MUSIC_BYTES)
    except ValueError:
        raise HTTPException(413, f"File musik melebihi batas {MAX_MUSIC_BYTES // (1024 * 1024)} MB")
    return {"name": dst.stem, "file": str(dst)}


@app.delete("/api/music")
def delete_music(file: str):
    f = Path(file).resolve()
    if f.parent != effects.MUSIC_DIR.resolve() or not f.is_file():
        raise HTTPException(404, "Musik tidak ditemukan")
    f.unlink()
    return effects.list_music()


@app.get("/api/music/play")
def play_music(file: str):
    f = Path(file).resolve()
    if f.parent != effects.MUSIC_DIR.resolve() or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _get(pid)


@app.delete("/api/projects/{pid}")
def del_project(pid: str):
    _get(pid)
    project.delete(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/cancel")
def cancel(pid: str):
    _get(pid)
    project.cancel(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/retry")
def retry(pid: str):
    _get(pid)
    return project.retry(pid)


@app.post("/api/projects/{pid}/rerender")
def rerender(pid: str, body: Settings):
    _get(pid)
    return project.rerender_all(pid, body.settings)


@app.post("/api/projects/{pid}/settings")
def project_settings(pid: str, body: ProjectSettings):
    """Simpan gaya proyek (berlaku untuk render berikutnya); rerender=true langsung render ulang klip yang sudah jadi."""
    _get(pid)
    if body.rerender:
        return project.rerender_all(pid, body.settings)
    return project.update_settings(pid, body.settings)


@app.get("/api/projects/{pid}/words")
def project_words(pid: str, start: float = 0, end: float = 1e9):
    """Kata transkrip (waktu absolut) dalam rentang — untuk preview caption langsung di studio."""
    _get(pid)
    f = project.pdir(pid) / "transcript.json"
    if not f.exists():
        return {"words": []}
    words = project.resolve_caption_track(pid)
    return {"words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in words if start - 0.05 <= w["s"] <= end + 0.05]}


def _clip_words_full(pid: str, cid: str):
    """(proyek, klip, kata relatif klip lengkap dengan probabilitas) atau 404."""
    from . import wordtools

    p = _get(pid)
    clip = next((c for c in p.get("clips", []) if c.get("id") == cid), None)
    if not clip:
        raise HTTPException(404, "Klip tidak ditemukan")
    if "start" not in clip or "end" not in clip:
        raise HTTPException(409, "Data klip lama belum memiliki waktu mulai/akhir. Buat ulang kandidat atau render klip ini.")
    tw = project.resolve_caption_track(pid)
    return p, clip, wordtools.clip_words_with_p(tw, clip)


@app.get("/api/projects/{pid}/clips/{cid}/quality")
def clip_quality(pid: str, cid: str, low: float = 0.55):
    """Saran kualitas transkrip: filler, kata berulang, kata low-confidence + pratinjau potong jeda."""
    from . import wordtools

    p, clip, words = _clip_words_full(pid, cid)
    cfg = {**DEFAULTS, **p.get("settings", {}), **(clip.get("overrides") or {})}
    dur = float(clip["end"]) - float(clip["start"])
    return {"quality": wordtools.analyze(words, max(0.05, min(0.95, low))),
            "silence": wordtools.silence_preview(words, dur, float(cfg.get("silence_gap", 0.55))),
            "cut_silence": bool(cfg.get("cut_silence"))}


@app.get("/api/projects/{pid}/clips/{cid}/subtitles")
def clip_subtitles(pid: str, cid: str, format: str = "srt", word_timing: bool = False, per_line: int = 5, download: bool = True):
    """Ekspor subtitle klip: srt | vtt | sbv | ass | txt. Waktu mengikuti video hasil (jeda terpotong bila aktif)."""
    from . import wordtools

    p, clip, words = _clip_words_full(pid, cid)
    cfg = {**DEFAULTS, **p.get("settings", {}), **(clip.get("overrides") or {})}
    words = wordtools.timeline_words(words, float(clip["end"]) - float(clip["start"]), cfg)
    if not words:
        raise HTTPException(404, "Klip ini belum punya kata transkrip")
    try:
        body = wordtools.export_subtitles(words, format, max(1, min(12, per_line)), word_timing=word_timing)
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))
    headers = {"Content-Disposition": f'attachment; filename="{cid}.{format.lower()}"'} if download else {}
    return Response(body, media_type=wordtools.FORMATS[format.lower()] + "; charset=utf-8", headers=headers)


@app.get("/api/projects/{pid}/clips/{cid}/delivery")
def clip_delivery(pid: str, cid: str, platform: str = "all"):
    """Ukur file klip hasil render terhadap aturan platform: rasio, durasi, audio, loudness."""
    from . import delivery

    p = _get(pid)
    clip = next((c for c in p.get("clips", []) if c.get("id") == cid), None)
    if not clip:
        raise HTTPException(404, "Klip tidak ditemukan")
    f = project.pdir(pid) / clip["file"] if clip.get("file") else None
    if not f or clip.get("status") != "done" or not f.is_file():
        raise HTTPException(409, "Klip belum selesai dirender")
    try:
        cached = clip.get("delivery")
        if cached and not clip.get("needs_rerender"):
            return cached if platform == "all" else cached[delivery.platform_id(platform)]
        return delivery.check_all(f) if platform == "all" else delivery.check(f, platform)
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


@app.post("/api/projects/{pid}/clips/{cid}/exports/{platform}", status_code=202)
def create_platform_export(pid: str, cid: str, platform: str):
    from . import platform_export

    _get(pid)
    try:
        return platform_export.enqueue(pid, cid, platform)
    except KeyError:
        raise HTTPException(404, "Klip tidak ditemukan") from None
    except ValueError as exc:
        raise HTTPException(409 if isinstance(exc, platform_export.ExportBlocked) else 400, redact(str(exc))) from None


@app.get("/api/projects/{pid}/clips/{cid}/exports/{platform}")
def platform_export_status(pid: str, cid: str, platform: str):
    from . import delivery

    p = _get(pid)
    try:
        platform = delivery.platform_id(platform)
    except ValueError as exc:
        raise HTTPException(400, redact(str(exc))) from None
    clip = next((c for c in p.get("clips", []) if c["id"] == cid), None)
    if clip is None:
        raise HTTPException(404, "Klip tidak ditemukan")
    return (clip.get("exports") or {}).get(platform, {"platform": platform, "status": "not_started"})


@app.get("/api/projects/{pid}/clips/{cid}/exports/{platform}/download")
def download_platform_export(pid: str, cid: str, platform: str):
    from . import platform_export, delivery

    _get(pid)
    try:
        file = platform_export.download(pid, cid, platform)
        return FileResponse(file, media_type="video/mp4", filename=f"{cid}-{delivery.platform_id(platform)}.mp4",
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
    except KeyError:
        raise HTTPException(404, "Klip tidak ditemukan") from None
    except ValueError as exc:
        raise HTTPException(409 if isinstance(exc, platform_export.ExportBlocked) else 400, redact(str(exc))) from None


@app.get("/api/clips")
def all_clips(limit: int = 200):
    """Galeri semua klip yang sudah dirender, lintas proyek (terbaru dulu)."""
    out = []
    for item in project.list_projects():
        try:
            p = project.load(item["id"])
        except KeyError:
            continue
        for c in p.get("clips", []):
            if c.get("status") == "done" and c.get("file"):
                out.append({"project_id": p["id"], "project_title": p.get("title"), "id": c["id"], "title": c.get("title"),
                            "score": c.get("score"), "duration": c.get("duration"), "file": c["file"], "thumb": c.get("thumb"),
                            "version": c.get("version"), "created": p.get("created")})
    return out[:limit]


@app.post("/api/projects/{pid}/candidates/select")
def select_candidates(pid: str, body: CandidateSelection):
    _get(pid)
    return project.select_candidates(pid, body.ids)


@app.post("/api/projects/{pid}/candidates/top/{count}")
def select_top(pid: str, count: int):
    p = _get(pid)
    count = max(1, min(30, count))
    return project.select_candidates(pid, [x["id"] for x in p.get("candidates", [])[:count]])


@app.post("/api/projects/{pid}/candidates/{cid}/action")
def candidate_action(pid: str, cid: str, body: CandidateAction):
    _get(pid)
    try:
        return project.candidate_action(pid, cid, body.action, body.value)
    except KeyError:
        raise HTTPException(404, "Kandidat tidak ditemukan")
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


@app.post("/api/projects/{pid}/rerank")
def rerank_candidates(pid: str, body: Settings):
    _get(pid)
    return project.rerank_candidates(pid, body.settings)


@app.post("/api/projects/{pid}/batch-render")
def batch_render(pid: str, body: CandidateSelection):
    _get(pid)
    return project.batch_render(pid, body.ids or None)


@app.get("/api/projects/{pid}/candidates/manifest")
def candidate_manifest(pid: str):
    _get(pid)
    f = project.pdir(pid) / "candidate-manifest.json"
    if not f.exists():
        raise HTTPException(404, "Manifest kandidat belum tersedia")
    return FileResponse(f, media_type="application/json", filename="candidate-manifest.json")


@app.patch("/api/projects/{pid}/clips/{cid}")
def edit(pid: str, cid: str, body: ClipEdit):
    _get(pid)
    try:
        return project.edit_clip(pid, cid, body.changes, body.rerender)
    except KeyError:
        raise HTTPException(404, "Klip tidak ditemukan")
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


@app.get("/api/projects/{pid}/captions")
def get_caption_workspace(pid: str):
    _get(pid)
    return project.load_caption_workspace(pid)


@app.put("/api/projects/{pid}/captions")
def save_caption_workspace(pid: str, body: CaptionWorkspaceSave):
    _get(pid)
    try:
        return project.save_caption_workspace(pid, body.data, body.revision)
    except ValueError as e:
        raise HTTPException(409 if "proses lain" in redact(str(e)) else 400, redact(str(e)))


@app.post("/api/projects/{pid}/captions/action")
def caption_workspace_action(pid: str, body: CaptionWorkspaceAction):
    _get(pid)
    try:
        return project.caption_action(pid, body.action, body.payload)
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


@app.get("/api/caption-templates")
def caption_templates():
    from .caption_workspace import TEMPLATES

    return TEMPLATES


@app.get("/api/projects/{pid}/frame")
def frame(pid: str, t: float = 0.0):
    p = _get(pid)
    m = p.get("media")
    if not m:
        raise HTTPException(409, "Video belum siap")
    d = project.pdir(pid)
    out = d / f"frame_{int(t * 10)}.jpg"
    if not out.exists():
        if m.get("remote"):
            from . import download

            try:
                download.grab_remote_frame(p["source"], t, out, width=640, max_h=download.source_height(p.get("settings"), True))
            except Exception as e:  # noqa: BLE001
                raise HTTPException(502, f"Frame dari sumber online gagal diambil: {redact(str(e))[:200]}") from None
        else:
            media.grab_frame(d / m["file"], t, out, width=640)
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.post("/api/projects/{pid}/detect-facecam")
def detect_facecam_api(pid: str):
    _get(pid)
    try:
        return project.redetect_facecam(pid)
    except ValueError as e:
        raise HTTPException(409, redact(str(e)))


@app.get("/api/projects/{pid}/source")
def source_video(pid: str):
    p = _get(pid)
    if not p.get("media"):
        raise HTTPException(409, "Video belum siap")
    if p["media"].get("remote"):
        raise HTTPException(409, "Mode hemat disk: video penuh tidak disimpan. Pratinjau memakai frame dan klip hasil render.")
    return FileResponse(project.pdir(pid) / p["media"]["file"])


@app.get("/api/production")
def production_board():
    projects = project.list_projects()
    groups = {"draft_candidate": [], "selected": [], "rendering": [], "ready": [], "published_archived": []}
    for item in projects:
        try:
            full = project.load(item["id"])
        except KeyError:
            continue
        candidates_list = full.get("candidates", [])
        if full.get("status") == "done": state = "ready"
        elif full.get("status") in {"running", "rendering"}: state = "rendering"
        elif any(x.get("selected") for x in candidates_list): state = "selected"
        else: state = full.get("production", {}).get("status", "draft_candidate")
        groups.setdefault(state, []).append({**item, "candidate_count": len(candidates_list),
                                             "selected_count": sum(bool(x.get("selected")) for x in candidates_list),
                                             "ready_count": sum(x.get("status") == "done" for x in candidates_list),
                                             "output_duration": round(sum(float(x.get("duration", 0)) for x in candidates_list if x.get("status") == "done"), 1)})
    return {"groups": groups, "metrics": {"projects": sum(len(v) for v in groups.values()),
            "candidates": sum(x["candidate_count"] for v in groups.values() for x in v),
            "ready": len(groups.get("ready", []))}}


@app.get("/files/{pid}/{name}")
def files(pid: str, name: str):
    try:
        d = project.pdir(pid)
    except KeyError:
        raise HTTPException(404)
    f = (d / name).resolve()
    if f.parent != d.resolve() or not f.is_file() or f.suffix not in {".mp4", ".jpg", ".ass", ".srt"}:
        raise HTTPException(404)
    return FileResponse(f)


@app.post("/api/projects/{pid}/open-folder")
def open_folder(pid: str):
    d = project.pdir(pid)
    if not d.exists():
        raise HTTPException(404)
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", str(d)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(d)])
    else:
        subprocess.Popen(["xdg-open", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "path": str(d)}


class NewClip(BaseModel):
    start: float
    end: float
    title: str = ""


class Template(BaseModel):
    name: str
    settings: dict


@app.post("/api/projects/{pid}/clips")
def add_clip(pid: str, body: NewClip):
    _get(pid)
    try:
        return project.add_clip(pid, body.start, body.end, body.title)
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


class ExportReq(BaseModel):
    folder: str = ""


@app.get("/api/projects/{pid}/summary")
def project_summary(pid: str):
    """Ringkasan ramah agent: path absolut video/SRT/thumbnail + caption & hashtag."""
    return automation.summary(_get(pid))


@app.post("/api/projects/{pid}/export")
def export_project(pid: str, body: ExportReq):
    p = _get(pid)
    if not any(c.get("status") == "done" for c in p["clips"]):
        raise HTTPException(409, "Belum ada klip yang selesai")
    if body.folder.strip():
        path = automation.auto_export({**p, "settings": {**p["settings"], "export_dir": body.folder.strip()}})
        return {"folder": path}
    return {"zip": str(project.zip_project(pid))}


class HookTest(BaseModel):
    url: str


@app.post("/api/automation/test-webhook")
def test_webhook(body: HookTest):
    import urllib.request

    url = body.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL webhook harus diawali http(s)://")
    payload = json.dumps({"event": "test", "message": "Tes webhook dari ClipperCuan"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "ClipperCuan"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"ok": True, "status": r.status}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Webhook gagal: {redact(str(e))}")


@app.get("/api/agent/info")
def agent_info():
    """Info untuk menyambungkan AI agent: perintah MCP siap pakai."""
    import os as _os
    import sys as _sys

    app_dir = str(Path(__file__).resolve().parent.parent)
    py = _os.path.normpath(_sys.executable)  # normpath, bukan realpath: jangan keluar dari venv
    if getattr(_sys, "frozen", False):  # paket .exe/.app: panggil langsung executable-nya
        server_cfg = {"command": py, "args": ["mcp"]}
        cli = f'"{py}" cli'
    else:
        server_cfg = {"command": py, "args": ["-m", "clipper", "mcp"], "cwd": app_dir, "env": {"PYTHONPATH": app_dir}}
        cli = f'cd "{app_dir}" && "{py}" -m clipper cli'
    return {"python": py, "app_dir": app_dir, "inbox_dir": str(automation.INBOX_DIR), "cli": cli,
            "mcp_config": {"mcpServers": {"clippercuan": server_cfg}},
            "api_docs": "/docs"}


@app.post("/api/automation/inbox/scan")
def inbox_scan():
    return {"created": automation.scan_inbox_once(), "inbox": str(automation.INBOX_DIR)}


@app.delete("/api/projects/{pid}/clips/{cid}")
def del_clip(pid: str, cid: str):
    _get(pid)
    return project.delete_clip(pid, cid)


@app.get("/api/projects/{pid}/zip")
def zip_all(pid: str):
    p = _get(pid)
    if not any(c.get("status") == "done" for c in p["clips"]):
        raise HTTPException(409, "Belum ada klip yang selesai")
    f = project.zip_project(pid)
    safe = "".join(ch for ch in p.get("title", pid) if ch.isalnum() or ch in " -_").strip()[:50] or pid
    return FileResponse(f, media_type="application/zip", filename=f"{safe} - klip.zip")


@app.get("/api/templates")
def templates():
    return project.list_templates()


@app.post("/api/templates")
def save_template(body: Template):
    try:
        return project.save_template(body.name, body.settings)
    except ValueError as e:
        raise HTTPException(400, redact(str(e)))


@app.delete("/api/templates/{name}")
def delete_template(name: str):
    return project.delete_template(name)


@app.get("/api/system")
def system():
    """Cek sistem: ffmpeg, GPU, model terunduh, ruang disk, versi komponen."""
    import platform
    import subprocess as sp

    from .config import FFMPEG, MODELS_DIR

    out: dict = {"python": platform.python_version(), "os": f"{platform.system()} {platform.release()} ({platform.machine()})"}
    try:
        r = sp.run([FFMPEG, "-hide_banner", "-version"], capture_output=True, text=True, timeout=15, creationflags=media._NO_WINDOW)
        f = sp.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=15, creationflags=media._NO_WINDOW)
        out["ffmpeg"] = {"path": FFMPEG, "version": r.stdout.split("\n")[0], "libass": " ass " in f.stdout}
        out["encoders"] = media.encoders()
    except Exception as e:  # noqa: BLE001
        out["ffmpeg"] = {"path": FFMPEG, "error": redact(str(e))}
    try:
        import ctranslate2

        out["gpu_cuda"] = ctranslate2.get_cuda_device_count()
    except Exception:
        out["gpu_cuda"] = 0
    for mod in ("yt_dlp", "faster_whisper", "cv2", "fastapi"):
        try:
            m = __import__(mod)
            out.setdefault("versions", {})[mod] = getattr(m, "__version__", None) or getattr(getattr(m, "version", None), "__version__", "?")
        except Exception:
            out.setdefault("versions", {})[mod] = None
    out["models"] = sorted({d.name.replace("models--Systran--faster-whisper-", "") for d in MODELS_DIR.glob("models--*")})
    du = shutil.disk_usage(DATA_DIR)
    out["disk_free_gb"] = round(du.free / 1e9, 1)
    out["data_size_gb"] = round(sum(f.stat().st_size for f in DATA_DIR.rglob("*") if f.is_file()) / 1e9, 2)
    return out


@app.get("/api/settings")
def get_settings():
    return llm.public_settings()


@app.post("/api/settings")
def set_settings(body: Settings):
    llm.save_settings(body.settings)
    return llm.public_settings()


@app.post("/api/asr/test")
def asr_test(body: Settings):
    """Tes API transkripsi cloud memakai nilai form (belum disimpan)."""
    c = {**llm.load_settings()["asr"], **{k: v for k, v in body.settings.get("asr", {}).items() if v != "••••"}}
    if not c.get("base_url") or not c.get("model"):
        raise HTTPException(400, "Isi Base URL dan model")
    try:
        asr.test_api(c)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, redact(str(e))[:300])


@app.get("/api/llm/catalog")
def llm_catalog():
    """Daftar model Gemini + GPT-5.6 Think Deeper dan rantai fallback aktif."""
    return {**llm.model_catalog(), "chain_posts": llm.chain_for("posts"), "chain_moments": llm.chain_for("moments")}


@app.get("/api/llm/check")
def llm_check(refresh: bool = False):
    """Status pemeriksaan berkala model 9Router; refresh=true memeriksa langsung."""
    if refresh or not _MODEL_CHECK.get("checked_at"):
        return _check_model_catalog()
    return _MODEL_CHECK


@app.post("/api/llm/models")
def llm_models(body: Settings):
    """Tes koneksi + ambil daftar model memakai nilai form (belum disimpan)."""
    c = {**llm.cfg(), **{k: v for k, v in body.settings.get("llm", {}).items() if v != "••••"}}
    try:
        return {"models": llm.list_models(c)}
    except llm.LLMError as e:
        raise HTTPException(502, redact(str(e)))


@app.post("/api/projects/{pid}/clips/{cid}/ai")
def clip_ai(pid: str, cid: str, kind: str = "titles"):
    p = _get(pid)
    clip = next((c for c in p["clips"] if c["id"] == cid), None)
    if not clip:
        raise HTTPException(404, "Klip tidak ditemukan")
    if not llm.active("moments") and not llm.active("titles"):
        raise HTTPException(400, "Aktifkan LLM di Pengaturan dulu")
    text = clip.get("text") or " ".join(w["w"] for w in clip.get("words") or [])
    try:
        if kind == "post":
            return llm.make_post(text, clip.get("title", ""), p.get("language"), p.get("content_profile") or "general")
        return {"titles": llm.make_title(text, p.get("language"))}
    except llm.LLMError as e:
        raise HTTPException(502, redact(str(e)))


@app.exception_handler(media.FFmpegError)
def _ffmpeg_err(_, exc):
    return JSONResponse({"detail": redact(str(exc))[-600:]}, status_code=500)


app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")  # preview caption memakai font yang sama dengan render
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
