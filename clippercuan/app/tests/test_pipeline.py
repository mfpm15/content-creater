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
