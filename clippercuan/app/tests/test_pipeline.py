"""Regresi alur utama: pipeline → render → proyek selesai, serta konsistensi clips/candidates."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from clipper import candidates, highlights, project, transcribe  # noqa: E402
from clipper.config import FFMPEG  # noqa: E402
from clipper.server import _local_request_ok  # noqa: E402

SENTENCES = ["Kenapa uang kamu selalu habis di tengah bulan?", "Ternyata rahasia nya ada di kebiasaan kecil.",
             "Jangan pernah beli barang sebelum tidur.", "Ini kesalahan terbesar yang sering dilakukan orang.",
             "Gaji lima juta bisa jadi cukup kalau kamu atur.", "Pertama catat semua pengeluaran harian kamu.",
             "Kedua pisahkan tabungan di hari gajian.", "Ketiga hindari cicilan yang tidak perlu."]


def fake_transcript(repeat: int = 2) -> dict:
    words, segs, t = [], [], 1.0
    for _ in range(repeat):
        for s in SENTENCES:
            idx = []
            for w in s.split():
                idx.append(len(words))
                words.append({"w": w, "s": round(t, 3), "e": round(t + .35, 3), "p": .9})
                t += .4
            segs.append({"text": s, "s": words[idx[0]]["s"], "e": words[idx[-1]]["e"], "words": idx})
            t += .5
    return {"language": "id", "words": words, "segments": segs}


def test_context_dependency_and_title_options_regex():
    bd = highlights._candidate_breakdown("Dan itu bagus", "Dan itu bagus", "ok.", 2.5, .5, .9)
    assert bd["clarity"] < 100 and bd["penalties"]["context_dependency"] > 0
    assert highlights.title_options("Kenapa uang habis? Karena boros. Ini caranya!")[:2] == ["Kenapa uang habis?", "Karena boros"]


def test_unpunctuated_transcript_uses_pauses_as_sentence_end():
    segs = [{"text": "halo semua", "s": 0, "e": 1, "words": [0]}, {"text": "hari ini kita bahas", "s": 1.1, "e": 2, "words": [1]},
            {"text": "uang", "s": 3.0, "e": 4, "words": [2]}]
    assert not highlights._is_punctuated(segs)
    assert not highlights._clean_end(segs, [], 0, False)   # jeda 0,1 dtk: bukan akhir kalimat
    assert highlights._clean_end(segs, [], 1, False)       # jeda 1 dtk


def test_rerank_keeps_render_results_and_rendered_overlap():
    base = {"start": 0, "end": 20, "text": "a b c d e", "status": "done", "file": "x.mp4", "post": {"caption": "c"},
            "words": [{"w": "a", "s": 0, "e": 1}], "overrides": {"layout": "blur"}}
    other = {"start": 5, "end": 25, "text": "z y x w", "status": "selected"}
    out = candidates.rerank([{**base, "id": "a"}, {**other, "id": "b"}], "podcast")
    done = next(x for x in out if x["id"] == "a")
    assert done["file"] == "x.mp4" and done["post"] == {"caption": "c"} and done["overrides"] == {"layout": "blur"}


def test_load_merges_legacy_duplicate_lists():
    p = {"candidates": [{"id": "c1", "status": "queued", "title": "lama"}],
         "clips": [{"id": "c1", "status": "done", "file": "c1.mp4", "title": "baru"}, {"id": "clip_01", "manual": True, "status": "done"}]}
    project._unify_clips(p)
    assert p["clips"] is p["candidates"]
    c1 = next(c for c in p["clips"] if c["id"] == "c1")
    assert c1["status"] == "done" and c1["file"] == "c1.mp4" and c1["title"] == "baru"
    assert any(c["id"] == "clip_01" for c in p["clips"])


def test_local_request_guard():
    assert _local_request_ok("127.0.0.1:8765", "", "GET")
    assert _local_request_ok("localhost:8765", "http://localhost:8765", "POST")
    assert not _local_request_ok("evil.example:8765", "", "GET")                     # DNS rebinding
    assert not _local_request_ok("127.0.0.1:8765", "https://evil.example", "POST")   # CSRF lintas situs


@pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")
def test_pipeline_renders_and_finishes(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    src = tmp / "src.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=70",
                    "-f", "lavfi", "-i", "sine=f=300:d=70", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **k: fake_transcript())
    project.start_worker()
    p = project.create(str(src), {"clip_count": 2, "candidate_count": 4, "min_sec": 8, "max_sec": 20, "duration_preset": "custom",
                                  "auto_render": True, "smart_crop": False, "use_llm": False})
    end = time.time() + 240
    while time.time() < end:
        p = project.load(p["id"])
        if p["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(.5)
    assert p["status"] == "done", (p["status"], p["message"], p.get("error"))
    rendered = [c for c in p["candidates"] if c.get("status") == "done"]
    assert rendered and all((project.pdir(p["id"]) / c["file"]).stat().st_size > 5000 for c in rendered)
    # memilih ulang / pin tidak boleh menghapus hasil render
    project.candidate_action(p["id"], rendered[0]["id"], "pinned", True)
    p = project.load(p["id"])
    again = next(c for c in p["clips"] if c["id"] == rendered[0]["id"])
    assert again["status"] == "done" and again["file"] == rendered[0]["file"]


def _wait_done(pid: str, limit: float = 240) -> dict:
    end = time.time() + limit
    while time.time() < end:
        p = project.load(pid)
        if p["status"] in ("done", "error", "cancelled"):
            return p
        time.sleep(.5)
    return project.load(pid)


@pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")
def test_lite_mode_never_stores_full_video(monkeypatch):
    from clipper import download

    tmp = Path(tempfile.mkdtemp())
    v, a = tmp / "v.mp4", tmp / "a.m4a"   # stream terpisah seperti DASH YouTube
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=70",
                    "-an", "-c:v", "libx264", str(v)], check=True)
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=70", "-c:a", "aac", str(a)], check=True)
    meta = {"title": "Video online", "duration": 70.0, "width": 640, "height": 360, "fps": 24.0,
            "video": {"url": str(v), "headers": {}}, "audio": {"url": str(a), "headers": {}}}
    monkeypatch.setattr(download, "resolve_streams", lambda *a, **k: meta)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **k: fake_transcript())
    project.start_worker()
    p = project.create("https://example.com/watch?v=1", {"storage": "lite", "clip_count": 1, "candidate_count": 3, "min_sec": 8,
                                                          "max_sec": 15, "duration_preset": "custom", "auto_render": True,
                                                          "smart_crop": False, "transcriber": "local"})
    p = _wait_done(p["id"])
    assert p["status"] == "done", (p["message"], p.get("error"), [c.get("error") for c in p["clips"]])
    assert p["media"]["remote"] and p["media"]["file"] is None
    files = {f.name for f in project.pdir(p["id"]).iterdir()}
    assert not any(n.startswith("source.") or ".src." in n or n == "audio-source.m4a" for n in files), files
    done = [c for c in p["clips"] if c["status"] == "done"]
    assert done and (project.pdir(p["id"]) / done[0]["file"]).stat().st_size > 5000


def test_recipe_is_base_and_user_settings_win():
    s = project._with_recipe({"recipe": "podcast-hormozi", "caption": {"highlight": "#00FF00"}})
    assert s["caption"]["style"] == "keyword" and s["caption"]["words_per_line"] == 2
    assert s["caption"]["highlight"] == "#00FF00"


def test_caption_styles_box_toggle_keyword_glow_and_duo_title():
    from clipper import captions
    from clipper.config import DEFAULTS, deep_merge

    words = [{"w": w, "s": i * .4, "e": i * .4 + .35} for i, w in enumerate("kenapa bisnis bisa bangkrut".split())]
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "keyword", "box": True, "effect": "glow", "y_pct": 60, "highlight": "#FFC933"},
                                "title": {"enabled": True, "role": "hook", "preset": "duo", "duration": 3}})
    ass = captions.build_ass(words, "Kenapa bisnis bangkrut? Ini sebabnya", cfg, (1080, 1920), 3)
    assert "CapBox" in ass and r"\blur" in ass and r"\pos(540,1152)" in ass
    assert r"\fnInstrument Serif" in ass                    # kata kunci memakai font aksen
    assert "&H00000000&" in ass                              # teks gelap di atas kotak kuning terang
    assert "Ini sebabnya" in ass and "Kenapa bisnis bangkrut?" in ass


def test_studio_endpoints_recipes_settings_words_clips():
    from fastapi.testclient import TestClient

    from clipper.server import app

    with TestClient(app) as c:
        r = c.get("/api/recipes").json()
        assert {"podcast-box", "podcast-hormozi", "ml-hype", "clipping-campaign"} <= set(r["recipes"])
        assert c.get("/fonts/BarlowCondensed-ExtraBold.ttf").status_code == 200
        assert c.get("/api/projects", headers={"host": "evil.example"}).status_code == 403
        p = project.create("/nonexistent.mp4", {})          # proyek kosong cukup untuk uji endpoint pengaturan
        project.cancel(p["id"])
        out = c.post(f"/api/projects/{p['id']}/settings", json={"settings": {"caption": {"style": "keyword"}}}).json()
        assert out["settings"]["caption"]["style"] == "keyword" and out["settings"]["caption"]["font"]
        assert c.get(f"/api/projects/{p['id']}/words?start=0&end=5").json() == {"words": []}
        assert isinstance(c.get("/api/clips").json(), list)


def test_auto_clip_target_and_quality_gate():
    assert project.clip_target({"clip_count": "auto"}, 3600) == 10          # video 1 jam = 10 klip
    assert project.clip_target({"clip_count": 0}, 300) == 3                 # minimal 3
    assert project.clip_target({"clip_count": "auto"}, 6 * 3600) == 10      # maksimal 10
    assert project.clip_target({"clip_count": 5}, 3600) == 5
    ranked = [{"id": "a", "score": 80}, {"id": "b", "score": 30}, {"id": "c", "score": 60, "banned": True}, {"id": "d", "score": 50}]
    assert [x["id"] for x in project.auto_picks(ranked, 8)] == ["a", "d"]
    assert [x["id"] for x in project.auto_picks([{"id": "z", "score": 10}], 3)] == ["z"]   # tetap ada 1 klip


def test_detect_facecam_small_corner_face_vs_podcast():
    import numpy as np

    from clipper import facetrack

    class Fake:
        def __init__(self, faces):
            self.faces = faces

        def __call__(self, g):
            return self.faces

    frames = [np.zeros((360, 640), np.uint8)] * 6
    orig = facetrack._Detector
    try:
        facetrack._Detector = lambda w, h: Fake([(500, 260, 80, 80, None)])        # wajah kecil kanan bawah
        cam = facetrack.detect_facecam(frames)
        x, y, w, h = cam["rect"]
        fx, fy = (500 + 40) / 640, (260 + 40) / 360                                  # pusat wajah
        assert x <= fx <= x + w and y <= fy <= y + h and w < .5 and not cam["big_face"]
        facetrack._Detector = lambda w, h: Fake([(200, 40, 260, 280, None)])       # wajah besar = podcast
        assert facetrack.detect_facecam(frames)["big_face"] is True
        facetrack._Detector = lambda w, h: Fake([])
        assert facetrack.detect_facecam(frames)["rect"] is None
    finally:
        facetrack._Detector = orig


@pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")
def test_auto_recipe_gameplay_without_facecam_switches_to_blur_and_youtube_subs_skip_downloads(monkeypatch):
    from clipper import asr, download

    tmp = Path(tempfile.mkdtemp())
    v = tmp / "v.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=70",
                    "-f", "lavfi", "-i", "sine=f=300:d=70", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(v)], check=True)
    meta = {"title": "MLBB savage maniac gameplay", "duration": 70.0, "width": 640, "height": 360, "fps": 24.0,
            "video": {"url": str(v), "headers": {}}, "audio": {"url": str(v), "headers": {}}}
    monkeypatch.setattr(download, "resolve_streams", lambda *a, **k: meta)
    tr = {**fake_transcript(), "source": "youtube-auto"}
    monkeypatch.setattr(asr, "youtube_captions", lambda *a, **k: tr)
    def no_audio(*a, **k):
        raise AssertionError("audio tidak boleh diunduh bila subtitle YouTube ada")
    monkeypatch.setattr(download, "fetch_audio", no_audio)
    project.start_worker()
    p = project.create("https://www.youtube.com/watch?v=abc", {"storage": "lite", "recipe": "auto", "auto_render": True,
                                                              "clip_count": 1, "min_sec": 8, "max_sec": 15, "duration_preset": "custom"})
    p = _wait_done(p["id"])
    assert p["status"] == "done", (p["message"], p.get("error"), [c.get("error") for c in p["clips"]])
    assert p["content_profile"] == "mobile_legends" and p["settings"]["recipe_applied"] == "ml-hype"
    assert p["settings"]["layout"] == "blur" and p["settings"]["caption"]["y_pct"] == 76    # tanpa facecam → blur
    assert p["settings"]["duration_preset"] == "custom"                                       # pilihan pengguna menang
    assert not (project.pdir(p["id"]) / "audio.wav").exists()


def test_delete_clip_stays_deleted_after_reload():
    p = project.create("/nonexistent.mp4", {})
    project.cancel(p["id"])
    with project._LOCK:
        q = project.load(p["id"])
        q["candidates"] = q["clips"] = [{"id": "a", "status": "done"}, {"id": "b", "status": "done"}]
        project.save(q)
    project.delete_clip(p["id"], "a")
    assert [c["id"] for c in project.load(p["id"])["clips"]] == ["b"]


def test_finish_renders_waits_for_manual_clips_and_reports_failures():
    p = project.create("/nonexistent.mp4", {})
    project.cancel(p["id"])
    with project._LOCK:
        q = project.load(p["id"])
        q["candidates"] = q["clips"] = [{"id": "a", "status": "done", "selected": True}, {"id": "clip_01", "status": "queued", "manual": True}]
        project.save(q)
    assert project._finish_renders(p["id"]) is False          # klip manual masih antre
    project._set_clip(p["id"], "clip_01", status="error")
    assert project._finish_renders(p["id"]) is True
    q = project.load(p["id"])
    assert q["status"] == "done" and "1 gagal" in q["message"]
