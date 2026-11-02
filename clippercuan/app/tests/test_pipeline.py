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
from clipper.config import DEFAULTS, FFMPEG, deep_merge  # noqa: E402
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


def test_full_download_has_timeout_retry_and_visible_initial_progress():
    from pathlib import Path
    from clipper import download
    source = Path(download.__file__).read_text("utf-8")
    assert '"socket_timeout": 20' in source
    assert '"concurrent_fragment_downloads": 3' in source
    assert "Membaca metadata dan menyiapkan unduhan video penuh" in source
    assert "Mengunduh video penuh" in source


def test_source_identity_uses_platform_creator_and_safe_local_filename():
    from clipper import download
    remote = download.source_identity("https://www.youtube.com/watch?v=abc", {"extractor_key": "YouTube", "channel": "Kanal Resmi"})
    assert remote["label"] == "Sumber: YouTube · Kanal Resmi"
    local = download.source_identity(r"C:\video\episode-12.mp4")
    assert local["label"] == "Sumber: episode-12"
    assert len(remote["label"]) <= 80


def test_candidates_keep_plain_language_summary():
    item = candidates.normalize({"start": 0, "end": 20, "text": "A clear explanation.",
                                 "title": "Clear title", "summary": "This explains the central point."}, 1, "podcast", 30)
    assert item["summary"] == "This explains the central point."


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
    words = [{"w": w, "s": i * .4, "e": i * .4 + .35} for i, w in enumerate("kenapa bisnis bisa bangkrut".split())]
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "keyword", "box": True, "effect": "glow", "y_pct": 60,
                                             "highlight": "#FFC933", "accent_mode": "font",
                                             "accent_font": "Instrument Serif Italic"},
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
    assert project.clip_target({"clip_count": "auto"}, 3600) == 10          # jumlah kandidat target boleh tetap 10
    assert project.clip_target({"clip_count": 0}, 300) == 3                 # minimal 3
    assert project.clip_target({"clip_count": "auto"}, 6 * 3600) == 10      # maksimal 10 kandidat target
    assert project.clip_target({"clip_count": 5}, 3600) == 5
    ranked = [{"id": "a", "score": 80}, {"id": "b", "score": 30}, {"id": "c", "score": 60, "banned": True}, {"id": "d", "score": 50}]
    assert [x["id"] for x in project.auto_picks(ranked, 8)] == ["a", "d"]
    assert [x["id"] for x in project.auto_picks([{"id": "z", "score": 10}], 3)] == ["z"]   # tetap ada 1 klip


def test_auto_render_is_capped_to_top_five_ranked_candidates():
    ranked = [{"id": f"candidate_{i:02d}", "rank": i, "score": 90 - i} for i in range(1, 11)]
    picked = project.auto_picks(ranked, target=10)
    assert [x["rank"] for x in picked] == [1, 2, 3, 4, 5]
    assert all(x not in picked for x in ranked[5:])


def test_detect_facecam_small_corner_face_vs_podcast():
    import numpy as np

    from clipper import facetrack

    class Fake:
        """Koordinat wajah ditulis untuk frame 640 px; skalakan mengikuti ukuran frame yang dipakai detektor."""

        def __init__(self, faces):
            self.faces = faces

        def __call__(self, g):
            k = g.shape[1] / 640
            return [(int(x * k), int(y * k), int(w * k), int(h * k), m) for x, y, w, h, m in self.faces]

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


def test_detect_facecam_prefers_stable_corner_cluster_over_moving_game_faces():
    import numpy as np

    from clipper import facetrack

    class Seq:
        def __init__(self, per_frame):
            self.per_frame, self.i = per_frame, 0

        def __call__(self, g):
            k = g.shape[1] / 640
            faces = self.per_frame[self.i % len(self.per_frame)]
            self.i += 1
            return [(int(x * k), int(y * k), int(w * k), int(h * k), m) for x, y, w, h, m in faces]

    frames = [np.zeros((360, 640), np.uint8)] * 9
    orig = facetrack._Detector
    try:  # streamer di kiri bawah (stabil) + wajah karakter game yang berpindah-pindah di tengah
        per = [[(70, 270, 50, 52, None), (200 + 30 * k, 90 + 20 * k, 30, 30, None)] for k in range(9)]
        facetrack._Detector = lambda w, h: Seq(per)
        cam = facetrack.detect_facecam(frames)
        x, y, w, h = cam["rect"]
        assert x < .2 and y > .5 and w < .45                  # area facecam = pojok kiri bawah, bukan wajah karakter
    finally:
        facetrack._Detector = orig


def test_small_faces_away_from_corners_are_not_a_facecam():
    import numpy as np

    from clipper import facetrack

    class Two:   # podcast dua orang dari kamera lebar: dua wajah kecil di area tengah
        def __call__(self, g):
            k = g.shape[1] / 640
            return [(int(x * k), int(y * k), int(w * k), int(h * k), None) for x, y, w, h in ((200, 120, 60, 66), (380, 120, 60, 66))]

    frames = [np.zeros((360, 640), np.uint8)] * 8
    orig = facetrack._Detector
    try:
        facetrack._Detector = lambda w, h: Two()
        cam = facetrack.detect_facecam(frames)
        assert cam["rect"] is None and not cam["big_face"]
    finally:
        facetrack._Detector = orig


def test_adaptive_split_uses_profile_specific_composition(monkeypatch):
    rect = [0.0, 0.64, 0.27, 0.35]
    faces = [
        {"rect": [0.05, 0.05, 0.42, 0.78], "center": [.26, .3], "hits": 9, "confidence": .8},
        {"rect": [0.53, 0.05, 0.42, 0.78], "center": [.74, .3], "hits": 8, "confidence": .72},
    ]
    state = {"user_settings": {}, "facecam": {"rect": rect},
             "visual_composition": {"faces": faces, "confidence": .8}}
    monkeypatch.setattr(project, "load", lambda pid: state)
    monkeypatch.setattr(project, "update", lambda pid, **kw: None)
    base = deep_merge(DEFAULTS, {"recipe": "auto", "content_profile": "auto"})
    podcast = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), "podcast", {"confidence": .9})
    assert podcast["layout"] == "split"
    assert podcast["split"]["strategy"] == "dual-speaker"
    assert podcast["split"]["game"] == faces[0]["rect"] and podcast["split"]["face"] == faces[1]["rect"]
    # Presenter kecil (produk/layar mendominasi frame) → konteks di atas, presenter di bawah.
    small = {"rect": [0.62, 0.45, 0.3, 0.42], "center": [.77, .6], "hits": 9, "confidence": .8}
    state["visual_composition"] = {"faces": [small], "confidence": .8}
    review = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), "review", {"confidence": .9})
    assert review["layout"] == "split" and review["split"]["strategy"] == "context-presenter"
    # Presenter mengisi frame (wawancara WIRED: tinggi wilayah 0,75) → split akan menduplikasi orang yang sama; pakai crop wajah.
    big = {"rect": [0.3583, 0.0204, 0.3354, 0.7463], "center": [.526, .319], "hits": 10, "confidence": .833}
    state["visual_composition"] = {"faces": [big], "confidence": .833}
    for profile in ("review", "educational", "general"):
        full = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), profile, {"confidence": .9})
        assert full["layout"] == "portrait" and not full["split_decision"]["enabled"], profile
    state["visual_composition"] = {"faces": faces, "confidence": .8}
    for profile in ("gaming", "mobile_legends"):
        gaming = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), profile, {"confidence": .9})
        assert gaming["layout"] == "split" and gaming["split"]["face"] == rect
        assert gaming["split"]["game"][0] >= .27 - 1e-6


def test_adaptive_split_falls_back_when_composition_is_weak(monkeypatch):
    state = {"user_settings": {}, "facecam": {"rect": None},
             "visual_composition": {"faces": [], "confidence": .1}}
    monkeypatch.setattr(project, "load", lambda pid: state)
    monkeypatch.setattr(project, "update", lambda pid, **kw: None)
    base = deep_merge(DEFAULTS, {"recipe": "auto", "content_profile": "auto"})
    gaming = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), "gaming", {"confidence": .9})
    assert gaming["layout"] == "blur" and not gaming["split_decision"]["enabled"]
    podcast = project._apply_auto_recipe("x", deep_merge(DEFAULTS, base), "podcast", {"confidence": .9})
    assert podcast["layout"] == "portrait" and not podcast["split_decision"]["enabled"]


def test_split_areas_work_for_facecam_in_every_corner():
    from clipper import facetrack

    corners = {"kiri-atas": [0, 0, .27, .35], "kanan-atas": [.73, 0, .27, .35],
               "kiri-bawah": [0, .65, .27, .35], "kanan-bawah": [.73, .65, .27, .35]}
    for name, face in corners.items():
        a = facetrack.split_areas(face)
        gx, _, gw, gh = a["game"]
        assert a["face"] == face and gh == 1.0, name
        if name.startswith("kiri"):
            assert gx >= .27 - 1e-6 and abs(gx + gw - 1.0) < 1e-6, name       # kolom kiri (facecam) dibuang
        else:
            assert gx == 0.0 and gx + gw <= .73 + 1e-6, name                   # kolom kanan (facecam) dibuang
    wide = facetrack.split_areas([0.0, 0.7, 0.9, 0.3])                         # facecam melebar (bar bawah): gameplay utuh
    assert wide["game"] == [0.0, 0.0, 1.0, 1.0]


def test_detect_facecam_in_each_corner_from_stable_small_face():
    import numpy as np

    from clipper import facetrack

    class Fixed:
        def __init__(self, face):
            self.face = face

        def __call__(self, g):
            k = g.shape[1] / 640
            x, y, w, h = self.face
            return [(int(x * k), int(y * k), int(w * k), int(h * k), None)]

    frames = [np.zeros((360, 640), np.uint8)] * 8
    orig = facetrack._Detector
    try:
        for name, (fx, fy) in {"kiri-atas": (40, 20), "kanan-atas": (550, 20), "kiri-bawah": (40, 280), "kanan-bawah": (550, 280)}.items():
            facetrack._Detector = lambda w, h, f=(fx, fy, 50, 55): Fixed(f)
            x, y, w, h = facetrack.detect_facecam(frames)["rect"]
            cx, cy = (fx + 25) / 640, (fy + 27) / 360
            assert x <= cx <= x + w and y <= cy <= y + h, name
            assert (x < .5) == (fx < 320) and (y < .5) == (fy < 180), name       # sudut yang benar
    finally:
        facetrack._Detector = orig


def test_split_layout_puts_gameplay_on_top_and_facecam_below():
    from clipper import render
    from clipper.media import Probe

    cfg = {"split": {"face": [0, .64, .27, .36], "game": [0, 0, 1, 1], "face_ratio": .32}, "quality": {"sharpen": False}}
    graph = render.framing_filter("split", Probe(60, 1920, 1080, 30, True), cfg, None)
    assert graph.index("[top][bot]vstack") > 0
    assert "[a]crop=" in graph and "[bot]" in graph          # facecam → bot (bawah)
    assert "[gfg]" in graph and "[gbg][gfg]overlay" in graph  # gameplay utuh di atas dengan latar blur


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
