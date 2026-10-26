"""Server lokal (hanya 127.0.0.1) yang melayani UI dan API."""
from __future__ import annotations

import base64
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from contextlib import asynccontextmanager

from . import __version__, asr, automation, effects, llm, media, project
from .captions import FONT_PRESETS
from .config import DATA_DIR, DEFAULTS, FONTS_DIR, UPLOADS_DIR, WEB_DIR

@asynccontextmanager
async def lifespan(_app):
    project.start_worker()
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
    from . import candidates
    profiles = {name: {k: v for k, v in data.items() if k not in {"weights", "terms"}} for name, data in candidates.PROFILES.items()}
    return {"version": __version__, "data_dir": str(DATA_DIR), "defaults": DEFAULTS, "fonts": list(FONT_PRESETS),
            "profiles": profiles, "inbox_dir": str(automation.INBOX_DIR)}


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
    words = json.loads(f.read_text("utf-8")).get("words", [])
    return {"words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in words if start - 0.05 <= w["s"] <= end + 0.05]}


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
        raise HTTPException(400, str(e))


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
        raise HTTPException(400, str(e))


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
        raise HTTPException(409 if "proses lain" in str(e) else 400, str(e))


@app.post("/api/projects/{pid}/captions/action")
def caption_workspace_action(pid: str, body: CaptionWorkspaceAction):
    _get(pid)
    try:
        return project.caption_action(pid, body.action, body.payload)
    except ValueError as e:
        raise HTTPException(400, str(e))


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
                download.grab_remote_frame(p["source"], t, out, width=640)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(502, f"Frame dari sumber online gagal diambil: {str(e)[:200]}") from None
        else:
            media.grab_frame(d / m["file"], t, out, width=640)
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


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
    return {"groups": groups, "metrics": {"projects": len(projects),
            "candidates": sum(len(v) for v in [project.load(x["id"]).get("candidates", []) for x in projects]),
            "ready": sum(len(x) for x in groups.get("ready", []))}}


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
        raise HTTPException(400, str(e))


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
        raise HTTPException(502, f"Webhook gagal: {e}")


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
        raise HTTPException(400, str(e))


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
        out["ffmpeg"] = {"path": FFMPEG, "error": str(e)}
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
        raise HTTPException(502, str(e)[:300])


@app.post("/api/llm/models")
def llm_models(body: Settings):
    """Tes koneksi + ambil daftar model memakai nilai form (belum disimpan)."""
    c = {**llm.cfg(), **{k: v for k, v in body.settings.get("llm", {}).items() if v != "••••"}}
    try:
        return {"models": llm.list_models(c)}
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


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
            return llm.make_post(text, clip.get("title", ""), p.get("language"))
        return {"titles": llm.make_title(text, p.get("language"))}
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.exception_handler(media.FFmpegError)
def _ffmpeg_err(_, exc):
    return JSONResponse({"detail": str(exc)[-600:]}, status_code=500)


app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")  # preview caption memakai font yang sama dengan render
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
