"""Proyek = satu video sumber + hasil klip. Disimpan sebagai JSON di ~/ClipperCuan/projects/<id>/."""
from __future__ import annotations

import copy
import json
import os
import queue
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import asr, candidates, caption_workspace, download, highlights, llm, media, render, transcribe
from .config import DEFAULTS, PROJECTS_DIR, deep_merge

_LOCK = threading.RLock()
_JOBS: "queue.Queue[tuple[str, str, dict]]" = queue.Queue()
_CANCEL: set[str] = set()


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- penyimpanan
def pdir(pid: str) -> Path:
    if not pid or any(c in pid for c in "/\\.") :
        raise KeyError(pid)
    return PROJECTS_DIR / pid


def load(pid: str) -> dict:
    f = pdir(pid) / "project.json"
    if not f.exists():
        raise KeyError(pid)
    with _LOCK:
        p = json.loads(f.read_text("utf-8"))
        # Migrasi non-destruktif: proyek lama tetap memakai clips sebagai kandidat.
        p["schema_version"] = max(3, int(p.get("schema_version", 1)))
        _unify_clips(p)
        p.setdefault("rankings", candidates.rankings(p["candidates"]) if p["candidates"] else {})
        p.setdefault("production", {"status": "draft_candidate", "planned_date": "", "notes": "", "platform": ""})
        p.setdefault("caption_workspace", {"schema_version": 3, "revision": 0})
        return p


_RENDER_FIELDS = ("status", "file", "thumb", "srt", "ass", "words", "crop_keys", "overrides", "post", "title", "start", "end",
                  "duration", "version", "error", "cut_saved", "emojis", "caption_cues", "caption_layers",
                  "caption_provenance", "caption_render", "template_id", "template_name", "effective_caption_height_pct",
                  "sidecar_autoload_safe", "crop_confidence", "render_warnings", "manual")


def _unify_clips(p: dict) -> None:
    """`clips` dan `candidates` harus satu daftar yang sama (render & edit menulis ke clips, UI membaca candidates).

    Proyek lama menyimpan dua salinan yang bisa berbeda; hasil render/edit di `clips` dimenangkan atas salinan kandidat.
    """
    cands = p.get("candidates")
    clips = p.get("clips") or []
    if cands is None:
        p["candidates"] = clips
        return
    by_id = {c["id"]: c for c in cands}
    for clip in clips:
        base = by_id.get(clip["id"])
        if base is None:
            cands.append(clip)
            by_id[clip["id"]] = clip
        elif base is not clip:
            base.update({k: clip[k] for k in _RENDER_FIELDS if k in clip})
    p["clips"] = cands


def save(p: dict) -> None:
    with _LOCK:
        d = pdir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "project.json.tmp"
        caption_workspace.atomic_json(tmp, p)
        tmp.replace(d / "project.json")


def update(pid: str, **fields) -> dict:
    with _LOCK:
        p = load(pid)
        p.update(fields)
        p["updated"] = time.time()
        save(p)
        return p


def list_projects() -> list[dict]:
    out = []
    for f in PROJECTS_DIR.glob("*/project.json"):
        try:
            p = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        out.append({k: p.get(k) for k in ("id", "title", "status", "progress", "message", "created", "updated", "source")}
                   | {"clips": len(p.get("clips", [])), "thumb": next((c.get("thumb") for c in p.get("clips", []) if c.get("thumb")), None)})
    return sorted(out, key=lambda p: p.get("created") or 0, reverse=True)


def delete(pid: str) -> None:
    import shutil

    _CANCEL.add(pid)
    shutil.rmtree(pdir(pid), ignore_errors=True)


# ---------------------------------------------------------------- pembuatan
def _with_recipe(settings: dict) -> dict:
    """Resep gaya jadi dasar; pengaturan eksplisit dari pengguna tetap menang."""
    from .recipes import RECIPES

    base = DEFAULTS
    recipe = RECIPES.get(settings.get("recipe") or "")
    if recipe:
        base = deep_merge(DEFAULTS, recipe["settings"])
    return deep_merge(base, settings)


def create(source: str, settings: dict | None = None) -> dict:
    pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    p = {
        "id": pid, "schema_version": 3, "source": source, "title": "Memproses…", "status": "queued", "progress": 0.0,
        "message": "Menunggu antrean", "created": time.time(), "updated": time.time(), "owner": os.getpid(),
        "settings": _with_recipe(settings or {}), "user_settings": settings or {}, "clips": [], "candidates": [], "rankings": {},
        "production": {"status": "draft_candidate", "planned_date": "", "notes": "", "platform": ""}, "error": None,
    }
    save(p)
    _JOBS.put(("pipeline", pid, {}))
    return p


def cancel(pid: str) -> None:
    _CANCEL.add(pid)


def _progress(pid: str, lo: float, hi: float):
    last = [0.0]

    def cb(frac: float, msg: str):
        if pid in _CANCEL:
            raise Cancelled()
        now = time.time()
        if now - last[0] > 0.4 or frac >= 1:
            last[0] = now
            update(pid, progress=round(lo + (hi - lo) * max(0, min(frac, 1)), 3), message=msg)
    return cb


def _pipeline(pid: str) -> None:
    p = load(pid)
    cfg = p["settings"]
    work = pdir(pid)
    update(pid, status="running", message="Menyiapkan video…")

    lite = cfg.get("storage") == "lite" and download.is_url(p["source"])
    wav = work / "audio.wav"
    np_ = __import__("numpy")
    if lite:  # hemat disk: video penuh tidak pernah diunduh; potongan klip diambil saat render
        _progress(pid, 0.0, 0.18)(0.1, "Membaca info video (mode hemat)…")
        meta = download.resolve_streams(p["source"], max_h=download.source_height(cfg, True))
        title = meta["title"]
        src = None
        pr = media.Probe(meta["duration"], meta["width"], meta["height"], meta["fps"], True)
        update(pid, title=title, media={"file": None, "remote": True, "duration": pr.duration, "width": pr.width,
                                        "height": pr.height, "fps": pr.fps})

        def get_wav() -> Path:  # audio hanya diunduh bila subtitle YouTube tidak tersedia/tidak dipakai
            if not wav.exists():
                audio, _ = download.fetch_audio(p["source"], work, _progress(pid, 0.18, 0.2), max_h=download.source_height(cfg, True))
                media.extract_audio(audio, wav)
                audio.unlink(missing_ok=True)
            return wav

        if not pr.duration:  # situs tanpa info durasi → ukur dari audio
            import wave

            with wave.open(str(get_wav()), "rb") as w:
                pr = media.Probe(w.getnframes() / w.getframerate(), pr.width, pr.height, pr.fps, True)
            update(pid, media={**load(pid)["media"], "duration": pr.duration})
        tr = _transcript(pid, p["source"], cfg, work, get_wav, pr.duration)
        if not wav.exists() and cfg.get("lite_energy", False):
            get_wav()
        energy = media.audio_energy(wav) if wav.exists() else np_.zeros(1)
        update(pid, download_saved=("Subtitle YouTube dipakai: tidak ada audio/video penuh yang diunduh"
                                    if not wav.exists() else "Hanya audio yang diunduh"))
    else:
        src, title = download.fetch(p["source"], work, _progress(pid, 0.0, 0.18), max_h=download.source_height(cfg, False))
        pr = media.probe(src)
        # file lokal milik pengguna direferensikan dengan path absolut (tidak disalin)
        update(pid, title=title, media={"file": src.name if src.parent == work else str(src), "duration": pr.duration,
                                        "width": pr.width, "height": pr.height, "fps": pr.fps})
        if pr.has_audio:
            _progress(pid, 0.18, 0.2)(0, "Mengekstrak audio…")
            media.extract_audio(src, wav)
            tr = _transcript(pid, p["source"], cfg, work, lambda: wav, pr.duration)
            energy = media.audio_energy(wav)
        else:
            tr, energy = {"language": None, "words": [], "segments": []}, np_.zeros(1)

    visual = None
    if not lite:
        _progress(pid, 0.62, 0.65)(0, "Membaca aktivitas visual (scene & gerak)…")
        visual = media.visual_activity(src, pr.duration)
    _progress(pid, 0.62, 0.65)(0.2, "Membuat dan meranking kandidat…")
    target = clip_target(cfg, pr.duration)
    count = max(target + 3, min(30, int(cfg.get("candidate_count") or 10)))
    count = min(30, count)
    # profil & resep ditentukan dulu: resep otomatis ikut menentukan durasi, format, dan gaya
    classified = candidates.classify_profile(tr, {"title": title}, _activity(p, pr, src, tr, cfg))
    profile_name = cfg.get("content_profile", "auto")
    if profile_name == "auto":
        profile_name = classified["profile"]
    cfg = _apply_auto_recipe(pid, cfg, profile_name, classified)
    preset = cfg.get("duration_preset", "custom" if (cfg.get("min_sec"), cfg.get("max_sec")) != (15, 60) else "auto")
    if preset == "custom":
        mn, mx, duration_reason = float(cfg["min_sec"]), float(cfg["max_sec"]), "Rentang durasi kustom"
    else:
        mn, mx, duration_reason = highlights.duration_range(preset, tr)
    cfg["min_sec"], cfg["max_sec"] = mn, mx
    update(pid, settings=cfg, duration_estimate={"min": mn, "max": mx, "reason": duration_reason, "preset": preset},
           content_profile=profile_name, profile_classification=classified, clip_target=target)
    moments, engine = None, "lokal"
    if tr["segments"] and llm.active("moments") and cfg.get("use_llm", True):
        model = llm.cfg()["model_moments"]
        _progress(pid, 0.62, 0.65)(0.3, f"AI ({model}) memilih momen terbaik…")
        try:
            moments = _llm_moments(tr, energy, pr.duration, count, mn, mx, visual)
            engine = model
        except Exception as e:  # noqa: BLE001 — selalu ada cadangan lokal
            print(f"[llm] gagal, pakai skor lokal: {e}")
            update(pid, llm_warning=f"AI tidak tersedia ({str(e)[:200]}). Dipakai skor lokal.")
    if not moments:
        moments = highlights.find_moments(tr, energy, pr.duration, count, mn, mx, visual=visual)
    update(pid, engine=engine)
    lang = tr.get("language")
    prepared = []
    for i, m in enumerate(moments):
        post = highlights.post_kit(m.get("text", ""), m["title"], lang)
        m.setdefault("duration_reason", duration_reason)
        if m.get("hashtags"):
            post["hashtags"] = m["hashtags"]
        prepared.append({**m, "id": m.get("id", f"candidate_{i + 1:02d}"), "post": post,
                         "status": "draft_candidate", "words": None, "crop_keys": None})
    ranked = candidates.rerank(prepared, profile_name, float(cfg.get("diversity", .3)), float(cfg.get("max_overlap", .35)))[:count]
    manifest = candidates.manifest(ranked, profile_name, p["source"])
    (work / "candidate-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    update(pid, candidates=ranked, clips=ranked, rankings=manifest["rankings"], rights_checklist=manifest["rights_checklist"],
           language=lang, status="running" if cfg.get("auto_render") else "candidates_ready", progress=0.65,
           message=f"{len(ranked)} kandidat siap dipilih", viral_readiness=round(sum(x["score"] for x in ranked) / max(1, len(ranked))))
    if cfg.get("auto_render"):
        picks = auto_picks(ranked, target, float(cfg.get("min_score", 45)))
        select_candidates(pid, [x["id"] for x in picks])
        batch_render(pid)


def clip_target(cfg: dict, duration: float) -> int:
    """Jumlah klip yang dirender otomatis. "auto"/0: ±1 klip per 3 menit video, 3–10 (video ≥ 30 menit = 10 klip)."""
    raw = cfg.get("clip_count", "auto")
    if raw in (None, "", "auto", 0, "0"):
        return int(max(3, min(10, round((duration or 0) / 180))))
    return max(1, min(30, int(raw)))


def auto_picks(ranked: list[dict], target: int, min_score: float = 45) -> list[dict]:
    """Klip terbaik untuk render otomatis: urut ranking, lewati yang skornya terlalu lemah (minimal 1 klip)."""
    good = [x for x in ranked if not x.get("banned") and (x.get("pinned") or float(x.get("score", 0)) >= min_score)]
    return (good or ranked[:1])[:target]


def _sample_frames(p: dict, pr: media.Probe, src: Path | None, n: int = 8) -> list:
    """Beberapa frame merata (tanpa unduh video penuh di mode hemat) untuk deteksi facecam/gameplay."""
    import tempfile

    import cv2

    out = []
    times = [pr.duration * (i + 1) / (n + 1) for i in range(n)]
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            f = Path(td) / f"f{i}.jpg"
            try:
                if src is None:
                    download.grab_remote_frame(p["source"], t, f, width=640, max_h=download.source_height(p.get("settings"), True))
                else:
                    media.grab_frame(src, t, f, width=640)
                img = cv2.imread(str(f))
                if img is not None:
                    out.append(img)
            except Exception:  # noqa: BLE001 — sampel gagal: lanjut
                continue
    return out


def _activity(p: dict, pr: media.Probe, src: Path | None, tr: dict, cfg: dict) -> dict:
    """Sinyal non-teks untuk klasifikasi profil: gameplay (tanpa wajah besar + ujaran jarang/istilah game) & facecam."""
    from . import facetrack

    need = (cfg.get("content_profile", "auto") in ("auto", "mobile_legends") or cfg.get("recipe") == "auto"
            or (cfg.get("split") or {}).get("auto"))
    if not need or not pr.duration:
        return {}
    cam = facetrack.detect_facecam(_sample_frames(p, pr, src))
    coverage = caption_workspace.quality_report(tr, pr.duration)["coverage"] if tr.get("words") else 0.0
    gameplay = not cam["big_face"] and (cam["rect"] is not None or coverage < 0.35)
    update(p["id"], facecam=cam)
    return {"gameplay": gameplay, "facecam": cam["rect"], "speech_coverage": coverage}


def _apply_auto_recipe(pid: str, cfg: dict, profile_name: str, classified: dict) -> dict:
    """Resep "auto": pilih resep sesuai konten. Untuk gaming, split bila facecam terdeteksi, selain itu blur."""
    from .recipes import FALLBACK, RECIPES, default_for

    if cfg.get("recipe") == "auto" and not cfg.get("recipe_applied"):   # Ulangi tidak menimpa gaya yang sudah diedit
        # confidence hanya relevan bila profil berasal dari klasifikasi otomatis
        auto_profile = cfg.get("content_profile", "auto") == "auto"
        low = auto_profile and float((classified or {}).get("confidence", 1.0) or 0) < 0.5
        rid = FALLBACK if low else default_for(profile_name)
        look = {k: v for k, v in RECIPES[rid]["settings"].items() if k not in ("content_profile",)}
        if cfg.get("duration_preset") not in (None, "auto"):
            look.pop("duration_preset", None)
        if "watermark" in look:
            look["watermark"] = {**cfg.get("watermark", {}), **{k: v for k, v in look["watermark"].items() if k != "text"}}
        p = load(pid)
        cfg = deep_merge(deep_merge(cfg, look), p.get("user_settings") or {})  # pilihan eksplisit pengguna tetap menang
        cfg["recipe"], cfg["recipe_applied"] = "auto", rid
    p = load(pid)
    cam = p.get("facecam") or {}
    if cfg.get("layout") == "split" and (cfg.get("split") or {}).get("auto"):
        if cam.get("rect"):
            cfg["split"] = {**cfg["split"], "face": cam["rect"], "game": [0.0, 0.0, 1.0, 1.0]}
        else:  # gameplay tanpa facecam: gameplay utuh di tengah, caption di bawahnya (tidak menutup HUD)
            cfg["layout"] = "blur"
            cfg["caption"] = {**cfg["caption"], "y_pct": 76}
            cfg["layout_reason"] = "Facecam tidak terdeteksi: format Blur agar HUD & minimap tetap utuh"
    update(pid, settings=cfg)
    return cfg


def _transcript(pid: str, source: str, cfg: dict, work: Path, get_wav, duration: float) -> dict:
    """Rantai sumber subtitle: YouTube → API cloud → Whisper lokal (cadangan selalu tersedia)."""
    mode = cfg.get("transcriber", "auto")
    key = {"mode": mode, "model": cfg["model"], "language": cfg["language"], "translate_en": cfg["translate_en"]}
    cache = work / "transcript.json"
    if cache.exists():
        data = json.loads(cache.read_text("utf-8"))
        if data.get("_key") == key:
            return data
    cb = _progress(pid, 0.2, 0.62)
    notes: list[str] = []
    tr = None
    if mode in ("auto", "youtube") and asr.is_youtube(source) and not cfg["translate_en"]:
        cb(0.05, "Mengambil subtitle dari YouTube…")
        try:
            tr = asr.youtube_captions(source, cfg["language"])
            if not tr:
                notes.append("Video tidak punya subtitle YouTube")
        except Exception as e:  # noqa: BLE001
            notes.append(f"Subtitle YouTube gagal ({str(e)[:120]})")
    acfg = llm.load_settings()["asr"]
    use_api = mode == "api" or (mode == "auto" and bool(acfg.get("api_key")))
    if tr is None and use_api:
        try:
            tr = asr.api_transcribe(get_wav(), acfg, cfg["language"], cfg["translate_en"], duration, cb)
        except Exception as e:  # noqa: BLE001
            notes.append(f"Transkripsi cloud gagal ({str(e)[:160]})")
            tr = None
    if tr is None:
        tr = transcribe.transcribe(get_wav(), cfg["model"], cfg["language"], cfg["translate_en"], cb, duration)
        tr["source"] = "whisper-lokal"
    if notes:
        update(pid, asr_warning=" · ".join(notes) + f". Dipakai: {tr['source']}.")
    tr["_key"] = key
    tr["quality_report"] = caption_workspace.quality_report(tr, duration)
    caption_workspace.atomic_json(cache, tr)
    ws = caption_workspace.workspace(tr, duration, load(pid).get("content_profile", "podcast"))
    caption_workspace.atomic_json(work / "caption-workspace.json", ws)
    update(pid, transcript_source=tr.get("source"), transcription_quality=tr["quality_report"],
           caption_workspace={"schema_version": 3, "revision": ws["revision"], "recommended_template": ws["recommended_template"]})
    return tr


def _llm_moments(tr: dict, energy, duration: float, count: int, mn: float, mx: float, visual=None) -> list[dict]:
    """Ambil ±30 kandidat beragam dari skor lokal, biarkan LLM memilih & memberi judul."""
    segs = tr["segments"]
    pool = highlights.non_overlapping(highlights.score_candidates(tr, energy, mn, mx, visual=visual), 30, max_overlap=0.5)
    pool.sort(key=lambda c: c["s"])
    picks = llm.pick_moments([{"id": i + 1, "start": c["s"], "end": c["e"], "text": c["text"]} for i, c in enumerate(pool)],
                             count, tr.get("language"))
    chosen, meta = [], {}
    for pk in sorted(picks, key=lambda x: -x["score"]):
        if 1 <= pk["id"] <= len(pool):
            c = pool[pk["id"] - 1]
            fits = all(min(c["e"], o["e"]) - max(c["s"], o["s"]) < 0.15 * (c["e"] - c["s"]) for o in chosen)
            if c not in chosen and fits:
                chosen.append(c)
                meta[id(c)] = pk
        if len(chosen) >= count:
            break
    out = [highlights.to_moment(c, segs, duration, meta[id(c)]["score"], meta[id(c)]["title"] or None,
                                reason=meta[id(c)]["reason"], hashtags=meta[id(c)]["hashtags"],
                                confidence=meta[id(c)].get("confidence", c.get("confidence", .6)),
                                breakdown=meta[id(c)].get("breakdown") or c.get("breakdown", {}),
                                readiness=meta[id(c)]["score"]) for c in chosen]
    if len(out) < count:  # model memilih terlalu sedikit → lengkapi dari skor lokal
        extra = highlights.non_overlapping(highlights.score_candidates(tr, energy, mn, mx, visual=visual), count, taken=chosen)[len(chosen):]
        out += [highlights.to_moment(c, segs, duration, 70) for c in extra]
    out.sort(key=lambda m: m["score"], reverse=True)
    return out


def _render_one(pid: str, cid: str, words: list[dict] | None = None, pr: media.Probe | None = None) -> None:
    p = load(pid)
    work = pdir(pid)
    remote = p["media"].get("remote")
    src = None if remote else work / p["media"]["file"]
    pr = pr or (None if remote else media.probe(src))
    if words is None:
        tf = work / "transcript.json"
        words = json.loads(tf.read_text("utf-8"))["words"] if tf.exists() else []
    clip = next(c for c in p["clips"] if c["id"] == cid)
    cfg = deep_merge(p["settings"], clip.get("overrides"))
    _set_clip(pid, cid, status="rendering")
    seg = None
    try:
        if p["media"].get("remote"):  # mode hemat: ambil potongan klip saja, render, lalu hapus
            s0 = max(0.0, float(clip["start"]) - 1.0)
            e0 = min(float(p["media"]["duration"] or 1e9), float(clip["end"]) + 1.0)
            seg = download.fetch_segment(p["source"], s0, e0, work / f"{cid}.src.mkv", max_h=download.source_height(cfg, True))
            pr = media.probe(seg)
            clip = {**clip, "start": float(clip["start"]) - s0, "end": float(clip["end"]) - s0}
            words = [{**w, "s": w["s"] - s0, "e": w["e"] - s0} for w in words]
            src = seg
        res = render.render_clip(work, src, pr, clip, cfg, words)
        _set_clip(pid, cid, status="done", error=None, version=int(time.time()), **res)
        with _LOCK:
            latest = load(pid)
            _write_manifest(latest)
            save(latest)
    except Exception as e:
        _set_clip(pid, cid, status="error", error=str(e)[-1500:])
        raise
    finally:
        if seg is not None:
            seg.unlink(missing_ok=True)


def _set_clip(pid: str, cid: str, **fields) -> dict:
    with _LOCK:
        p = load(pid)
        for c in p["clips"]:
            if c["id"] == cid:
                c.update(fields)
                save(p)
                return c
    raise KeyError(cid)


# ---------------------------------------------------------------- edit klip
EDITABLE = {"title", "start", "end", "words", "crop_keys", "overrides", "post", "selected"}


def edit_clip(pid: str, cid: str, changes: dict, rerender: bool = True) -> dict:
    changes = {k: v for k, v in changes.items() if k in EDITABLE}
    p = load(pid)
    clip = next((c for c in p["clips"] if c["id"] == cid), None)
    if clip is None:
        raise KeyError(cid)
    dur = p.get("media", {}).get("duration") or 1e9
    if "start" in changes or "end" in changes:
        s = max(0.0, float(changes.get("start", clip["start"])))
        e = min(dur, float(changes.get("end", clip["end"])))
        if e - s < 1:
            raise ValueError("Durasi klip minimal 1 detik")
        changes["start"], changes["end"] = round(s, 2), round(e, 2)
        if "words" not in changes:
            changes["words"] = None       # hitung ulang dari transkrip
        if "crop_keys" not in changes:
            changes["crop_keys"] = None
    if "overrides" in changes:
        changes["overrides"] = deep_merge(clip.get("overrides") or {}, changes["overrides"])
        lay = changes["overrides"].get("layout")
        if lay and lay != deep_merge(p["settings"], clip.get("overrides")).get("layout"):
            changes.setdefault("crop_keys", None)
    _set_clip(pid, cid, **changes, status="queued" if rerender else clip.get("status"))
    if rerender:
        _JOBS.put(("render", pid, {"cid": cid}))
    return load(pid)


def add_clip(pid: str, start: float, end: float, title: str = "") -> dict:
    """Klip manual dari rentang pilihan pengguna."""
    with _LOCK:
        p = load(pid)
        if not p.get("media"):
            raise ValueError("Video belum siap")
        dur = p["media"]["duration"]
        s, e = max(0.0, float(start)), min(dur, float(end))
        if e - s < 1:
            raise ValueError("Durasi klip minimal 1 detik")
        n = max([int(c["id"].split("_")[-1]) for c in p["clips"]] + [0]) + 1
        tf = pdir(pid) / "transcript.json"
        words = json.loads(tf.read_text("utf-8"))["words"] if tf.exists() else []
        text = " ".join(w["w"] for w in words if s <= w["s"] <= e)
        title = title.strip() or (highlights.make_title([text]) if text else f"Klip {n}")
        clip = {"id": f"clip_{n:02d}", "start": round(s, 2), "end": round(e, 2), "score": 0, "title": title, "text": text,
                "reason": "dipilih manual", "post": highlights.post_kit(text, title, p.get("language")),
                "status": "queued", "words": None, "crop_keys": None, "manual": True}
        p["clips"].append(clip)
        save(p)
    _JOBS.put(("render", pid, {"cid": clip["id"]}))
    return load(pid)


def delete_clip(pid: str, cid: str) -> dict:
    with _LOCK:
        p = load(pid)
        p["candidates"] = p["clips"] = [c for c in p["clips"] if c["id"] != cid]
        save(p)
    for ext in (".mp4", ".jpg", ".ass", ".srt", ".src.mkv"):
        (pdir(pid) / f"{cid}{ext}").unlink(missing_ok=True)
    return p


def zip_project(pid: str) -> Path:
    """Semua klip + subtitle + teks posting dalam satu ZIP."""
    import zipfile

    p = load(pid)
    d = pdir(pid)
    out = d / "export.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        lines = []
        for i, c in enumerate(sorted(p["clips"], key=lambda c: (c.get("rank") or 999, -c.get("score", 0))), 1):
            if c.get("status") != "done" or not c.get("file"):
                continue
            safe = "".join(ch for ch in (c.get("title") or c["id"]) if ch.isalnum() or ch in " -_").strip()[:50] or c["id"]
            base = f"{int(c.get('rank') or i):02d} - {safe}"
            z.write(d / c["file"], base + ".mp4")
            if c.get("srt") and (d / c["srt"]).exists():
                z.write(d / c["srt"], base + ".srt")
            post = c.get("post") or {}
            lines.append(f"[{base}]\nJudul: {c.get('title', '')}\nCaption: {post.get('caption', '')}\n"
                         f"Hashtag: {' '.join(post.get('hashtags', []))}\n")
        z.writestr("caption-posting.txt", "\n".join(lines))
    return out


# ---------------------------------------------------------------- template gaya
def _tpl_file() -> Path:
    from .config import DATA_DIR

    return DATA_DIR / "templates.json"


def list_templates() -> dict:
    f = _tpl_file()
    try:
        return json.loads(f.read_text("utf-8")) if f.exists() else {}
    except Exception:
        return {}


def save_template(name: str, settings: dict) -> dict:
    name = name.strip()[:40]
    if not name:
        raise ValueError("Nama template kosong")
    t = list_templates()
    keep = {k: v for k, v in settings.items() if k not in ("watermark",)} | {"watermark": {**settings.get("watermark", {}), "image": ""}}
    t[name] = keep
    _tpl_file().write_text(json.dumps(t, ensure_ascii=False, indent=1), "utf-8")
    return t


def load_caption_workspace(pid: str) -> dict:
    p = load(pid)
    path = pdir(pid) / "caption-workspace.json"
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    transcript_path = pdir(pid) / "transcript.json"
    transcript = json.loads(transcript_path.read_text("utf-8")) if transcript_path.exists() else {"words": [], "segments": [], "source": p.get("transcript_source", "unknown")}
    data = caption_workspace.workspace(transcript, p.get("media", {}).get("duration", 0), p.get("content_profile", "podcast"))
    caption_workspace.atomic_json(path, data)
    return data


def save_caption_workspace(pid: str, payload: dict, expected_revision: int | None = None) -> dict:
    with _LOCK:
        current = load_caption_workspace(pid)
        if expected_revision is not None and int(expected_revision) != int(current.get("revision", 0)):
            raise ValueError("Workspace berubah di proses lain; muat ulang sebelum menyimpan")
        allowed = {"cues", "glossary", "selected_template", "custom_templates", "audit_trail", "undo_stack", "redo_stack"}
        previous = {k: current.get(k) for k in allowed}
        for key in allowed:
            if key in payload:
                current[key] = payload[key]
        current["undo_stack"] = (current.get("undo_stack") or [])[-19:] + [previous]
        current["redo_stack"] = []
        current["revision"] = int(current.get("revision", 0)) + 1
        current["updated_at"] = time.time()
        current["cues"] = caption_workspace.normalize_cues(current.get("cues") or [])
        current["caption_layers"] = 1
        current["layers"] = [{"role": "video", "active": True},
                             {"role": "hook", "active": bool((load(pid).get("settings", {}).get("title") or {}).get("enabled"))},
                             {"role": "spoken-caption", "active": True},
                             {"role": "emoji", "active": bool((load(pid).get("settings", {}).get("emoji") or {}).get("enabled"))}]
        validation = caption_workspace.validate_cues(current["cues"])
        current["validation"] = validation
        caption_workspace.atomic_json(pdir(pid) / "caption-workspace.json", current)
        p = load(pid)
        p["caption_workspace"] = {"schema_version": 3, "revision": current["revision"], "recommended_template": current.get("recommended_template")}
        save(p)
        return current


def caption_action(pid: str, action: str, payload: dict) -> dict:
    ws = load_caption_workspace(pid)
    cues = copy.deepcopy(ws.get("cues") or [])
    if action == "validate":
        ws["validation"] = caption_workspace.validate_cues(cues)
        return ws
    if action == "glossary":
        words, audit = caption_workspace.apply_glossary(ws.get("transcript", {}).get("words") or [], ws.get("glossary") or [])
        ws["transcript"]["words"] = words
        ws["cues"] = caption_workspace.cues(words)
        ws["audit_trail"] = (ws.get("audit_trail") or []) + audit
    elif action == "split":
        index = int(payload.get("index", -1)); at = int(payload.get("word", -1))
        if not (0 <= index < len(cues) and 0 < at < len(cues[index].get("words") or [])): raise ValueError("Posisi split tidak valid")
        cue = cues.pop(index); groups = [cue["words"][:at], cue["words"][at:]]
        cues[index:index] = [{"id": f"{cue['id']}-{n}", "start": g[0]["s"], "end": g[-1]["e"], "text": " ".join(w["w"] for w in g), "words": g} for n, g in enumerate(groups, 1)]
        ws["cues"] = cues
    elif action == "merge":
        index = int(payload.get("index", -1))
        if not 0 <= index < len(cues) - 1: raise ValueError("Posisi merge tidak valid")
        words = cues[index].get("words", []) + cues[index + 1].get("words", [])
        cues[index:index + 2] = [{"id": cues[index]["id"], "start": cues[index]["start"], "end": cues[index + 1]["end"], "text": " ".join(w["w"] for w in words), "words": words}]
        ws["cues"] = cues
    elif action == "shift":
        delta = max(-30, min(30, float(payload.get("delta", 0))))
        for cue in cues:
            cue["start"], cue["end"] = max(0, cue["start"] + delta), max(.05, cue["end"] + delta)
            for word in cue.get("words", []): word["s"], word["e"] = max(0, word["s"] + delta), max(.05, word["e"] + delta)
        ws["cues"] = cues
    elif action in {"undo", "redo"}:
        source, target = ("undo_stack", "redo_stack") if action == "undo" else ("redo_stack", "undo_stack")
        stack = ws.get(source) or []
        if not stack: return ws
        snapshot = stack.pop(); current = {k: ws.get(k) for k in snapshot}
        ws.update(snapshot); ws[source] = stack; ws[target] = (ws.get(target) or []) + [current]
    else:
        raise ValueError("Aksi editor tidak valid")
    return save_caption_workspace(pid, ws, ws.get("revision"))


def delete_template(name: str) -> dict:
    t = list_templates()
    t.pop(name, None)
    _tpl_file().write_text(json.dumps(t, ensure_ascii=False, indent=1), "utf-8")
    return t


def update_settings(pid: str, settings: dict) -> dict:
    with _LOCK:
        p = load(pid)
        p["settings"] = deep_merge(p["settings"], settings)
        p["updated"] = time.time()
        save(p)
        return p


def rerender_all(pid: str, settings: dict) -> dict:
    with _LOCK:
        p = load(pid)
        p["settings"] = deep_merge(p["settings"], settings)
        todo = [c for c in p["clips"] if c.get("selected") or c.get("status") in ("done", "error", "rendering", "queued") or c.get("manual")]
        for c in todo:
            c["status"] = "queued"
            if "layout" in settings:
                c["crop_keys"] = None
        if todo:
            p["status"], p["message"] = "rendering", f"{len(todo)} klip dirender ulang"
        save(p)
    for c in todo:
        _JOBS.put(("render", pid, {"cid": c["id"]}))
    return p


def _write_manifest(p: dict) -> None:
    data = candidates.manifest(p.get("candidates", []), p.get("content_profile", "podcast"), p.get("source", ""),
                               int(p.get("manifest_revision", 0)) + 1)
    cap = p.get("settings", {}).get("caption", {})
    data["render_settings"] = {"template_id": cap.get("template_id") or cap.get("preset") or "none/raw",
                               "font": cap.get("font"), "size_level": cap.get("size_level", "custom"),
                               "ass_size": cap.get("size"), "position": cap.get("position"), "y_pct": cap.get("y_pct"),
                               "max_lines": cap.get("max_lines", 2), "emphasis_mode": cap.get("accent_mode") if cap.get("style") == "keyword" else "none",
                               "caption_source": p.get("transcript_source", "transcript"), "caption_layers": 1}
    p["rankings"], p["rights_checklist"] = data["rankings"], data["rights_checklist"] | p.get("rights_checklist", {})
    p["manifest_revision"] = data["revision"]
    (pdir(p["id"]) / "candidate-manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def select_candidates(pid: str, ids: list[str]) -> dict:
    with _LOCK:
        p = load(pid)
        wanted = set(ids)
        for c in p["candidates"]:
            c["selected"] = c["id"] in wanted and not c.get("banned")
            if c["selected"] and c.get("status") == "draft_candidate":
                c["status"] = "selected"
        p["clips"] = p["candidates"]
        _write_manifest(p); save(p)
        return p


def candidate_action(pid: str, cid: str, action: str, value=True) -> dict:
    with _LOCK:
        p = load(pid)
        item = next((x for x in p["candidates"] if x["id"] == cid), None)
        if not item:
            raise KeyError(cid)
        if action not in {"pinned", "banned", "selected"}:
            raise ValueError("Aksi kandidat tidak valid")
        item[action] = bool(value)
        if action == "banned" and value:
            item["selected"] = False
        p["candidates"] = candidates.rerank(p["candidates"], p.get("content_profile", "podcast"),
                                              float(p["settings"].get("diversity", .3)),
                                              float(p["settings"].get("max_overlap", .35)))
        p["clips"] = p["candidates"]
        _write_manifest(p); save(p)
        return p


def rerank_candidates(pid: str, options: dict | None = None) -> dict:
    with _LOCK:
        p = load(pid); options = options or {}
        profile_name = options.get("profile", p.get("content_profile", "podcast"))
        p["content_profile"] = profile_name
        p["candidates"] = candidates.rerank(p["candidates"], profile_name,
                                              float(options.get("diversity", p["settings"].get("diversity", .3))),
                                              float(options.get("max_overlap", p["settings"].get("max_overlap", .35))))
        p["clips"] = p["candidates"]
        _write_manifest(p); save(p)
        return p


def batch_render(pid: str, ids: list[str] | None = None) -> dict:
    with _LOCK:
        p = load(pid)
        wanted = set(ids or [x["id"] for x in p["candidates"] if x.get("selected")])
        queued = 0
        for c in p["candidates"]:
            if c["id"] in wanted and c.get("status") not in {"queued", "rendering", "done"}:
                c["selected"], c["status"] = True, "queued"
                _JOBS.put(("render", pid, {"cid": c["id"]})); queued += 1
        if not queued:
            return p
        p["status"], p["message"] = "rendering", f"{queued} kandidat masuk antrean render"
        p["clips"] = p["candidates"]
        save(p); return p


# ---------------------------------------------------------------- worker
def _finish_renders(pid: str) -> bool:
    """Tandai proyek selesai bila tidak ada render tersisa. True bila baru saja selesai."""
    with _LOCK:
        p = load(pid)
        cands = p.get("candidates", [])
        if any(x.get("status") in ("queued", "rendering") for x in cands):   # termasuk klip manual & render ulang
            return False
        failed = sum(x.get("status") == "error" for x in cands)
        done = sum(x.get("status") == "done" for x in cands)
        msg = "Semua render terpilih selesai" if not failed else f"{done} klip selesai, {failed} gagal (lihat pesan error di kartu klip)"
        first = not p.get("done_notified")
        update(pid, status="done" if done or not failed else "error", progress=1.0, message=msg, done_notified=True)
        return first


def _worker() -> None:
    while True:
        kind, pid, extra = _JOBS.get()
        try:
            if kind == "pipeline":
                if pid in _CANCEL:
                    raise Cancelled()
                update(pid, done_notified=False)
                _pipeline(pid)
                st = load(pid).get("status")
                if st == "candidates_ready":
                    _notify(pid, "project.candidates_ready")
                # auto_render: notifikasi dikirim setelah render terakhir selesai
            elif kind == "render":
                err = None
                try:
                    _render_one(pid, extra["cid"])
                except KeyError:
                    raise
                except Exception as e:  # noqa: BLE001 — klip gagal tetap menutup proyek & mengirim notifikasi
                    err = e
                first = _finish_renders(pid)
                _notify(pid, "project.done" if first else "clip.rendered", extra["cid"])
                if err:
                    raise err
        except Cancelled:
            safe_update(pid, status="cancelled", message="Dibatalkan")
            _notify(pid, "project.cancelled")
        except KeyError:
            pass  # proyek dihapus saat antre
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            if kind == "pipeline":
                safe_update(pid, status="error", message=_friendly(e), error=traceback.format_exc()[-3000:])
                _notify(pid, "project.error")
        finally:
            _JOBS.task_done()


def _notify(pid: str, event: str, cid: str | None = None) -> None:
    """Webhook / ekspor otomatis. Render ulang satu klip hanya memicu webhook bila semua klip sudah beres."""
    from . import automation

    try:
        if event == "clip.rendered":
            p = load(pid)
            if p.get("status") not in ("done", "error") or any(c.get("status") in ("queued", "rendering") for c in p["clips"]):
                return
            event = "project.updated"
        automation.on_finished(pid, event)
    except Exception as e:  # noqa: BLE001
        print(f"[otomatisasi] {e}")


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if pid == os.getpid():
        return True
    try:
        if sys.platform.startswith("win"):
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259  # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except (OSError, AttributeError):
        return False


def safe_update(pid: str, **f) -> None:
    try:
        update(pid, **f)
    except Exception:
        pass


def _friendly(e: Exception) -> str:
    s = str(e)
    if "Sign in to confirm" in s or "bot" in s.lower():
        return ("YouTube meminta verifikasi. Buka Pengaturan → Unduhan, pilih browser yang sudah login YouTube "
                "(cookies), lalu klik Ulangi. Atau unduh videonya lalu pakai mode File.")
    if "Unsupported URL" in s:
        return "Link tidak didukung. Pakai link YouTube/TikTok/Instagram atau unggah file."
    if "unavailable" in s or "Private video" in s or "removed" in s:
        return "Video tidak tersedia (dihapus, privat, atau dibatasi wilayah). Periksa link-nya."
    if "HTTP Error 403" in s or "HTTP Error 429" in s:
        return "Server video menolak unduhan. Tutup lalu buka aplikasi lagi (pengunduh diperbarui), atau pakai mode File."
    if "Unable to download" in s or "timed out" in s.lower() or "Connection" in s:
        return "Gagal mengunduh — periksa koneksi internet lalu klik Ulangi."
    if isinstance(e, FileNotFoundError):
        return "File video tidak ditemukan. Unggah ulang lalu coba lagi."
    return s.splitlines()[0][:300] if s else e.__class__.__name__


def recover_interrupted() -> None:
    """Saat aplikasi dibuka lagi: tandai job yang terputus agar bisa diulang."""
    for f in PROJECTS_DIR.glob("*/project.json"):
        try:
            p = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        if p.get("status") in ("queued", "running"):
            if _pid_alive(p.get("owner", 0)) and p.get("owner") != os.getpid():
                continue  # sedang dikerjakan proses lain (mis. GUI dan CLI/agent berjalan bersamaan)
            p["status"], p["message"] = "error", "Terhenti karena aplikasi ditutup. Klik Ulangi."
            for c in p.get("clips", []):
                if c.get("status") in ("queued", "rendering"):
                    c["status"] = "error"
            save(p)


def retry(pid: str) -> dict:
    _CANCEL.discard(pid)
    p = load(pid)
    p["settings"]["caption_layers"] = 1
    p = update(pid, settings=p["settings"], status="queued", progress=0.0, message="Menunggu antrean", error=None, owner=os.getpid())
    _JOBS.put(("pipeline", pid, {}))
    return p


_started = False


def start_worker() -> None:
    global _started
    if not _started:
        _started = True
        recover_interrupted()
        threading.Thread(target=_worker, daemon=True, name="clipper-worker").start()
        from . import automation

        automation.start_inbox_watcher()
