"""render_clip memakai framing per-shot, dan tidak menganggap crop_keys hasil render lama sebagai keyframe manual."""
import shutil
import subprocess
from pathlib import Path

import pytest

from clipper import media, render, shots
from clipper.config import DEFAULTS, FFMPEG, deep_merge

needs_ffmpeg = pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")

PLAN = {"shots": [{"a": 0.0, "b": 2.0, "mode": "single", "keys": [[0.0, 0.5]], "zoom": 1.0, "cy": .4, "confidence": 1.0},
                  {"a": 2.0, "b": 3.5, "mode": "broll", "confidence": .8},
                  {"a": 3.5, "b": 6.0, "mode": "multi", "faces": [[.25, .4, .15, .26], [.75, .4, .14, .25]], "confidence": 1.0}],
        "confidence": .93, "source": "shots", "cuts": 2, "samples": 24, "face_samples": 20, "multi_shots": 1}


@pytest.fixture()
def source(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=6",
                    "-f", "lavfi", "-i", "sine=f=300:d=6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
    return src


def run(tmp_path, src, clip_extra=None, cfg_extra=None, cut=False):
    cfg = deep_merge(DEFAULTS, {"layout": "portrait", "smart_crop": True, "cut_silence": cut, **(cfg_extra or {})})
    pr = media.probe(src)
    clip = {"id": "clip_01", "start": 0.0, "end": 6.0, "title": "Uji", **(clip_extra or {})}
    words = [{"w": f"kata{i}", "s": i * .5, "e": i * .5 + .3} for i in range(10)]
    return render.render_clip(tmp_path, src, pr, clip, cfg, words)


@needs_ffmpeg
def test_stale_auto_keys_do_not_block_shot_framing(tmp_path, source, monkeypatch):
    monkeypatch.setattr(shots, "plan", lambda *a, **k: PLAN)
    res = run(tmp_path, source, {"crop_keys": [[0.0, 0.2], [3.0, 0.8]]})        # sisa render lama, bukan buatan pengguna
    assert res["framing"] == "shots" and res["tracking"]["cuts"] == 2
    assert res["crop_keys"] is None, "keyframe otomatis tidak disimpan lagi supaya render berikutnya dihitung ulang"
    out = media.probe(tmp_path / res["file"])
    assert (out.width, out.height) == (1080, 1920) and out.duration == pytest.approx(6.0, abs=0.3)


@needs_ffmpeg
def test_manual_keys_from_crop_studio_are_respected(tmp_path, source, monkeypatch):
    called = []
    monkeypatch.setattr(shots, "plan", lambda *a, **k: called.append(1) or PLAN)
    res = run(tmp_path, source, {"crop_keys": [[0.0, 0.3], [2.0, 0.7]]}, {"crop": {"hold": True}})
    assert not called and res["framing"] == "tracking" and res["tracking"]["source"] == "manual"
    res2 = run(tmp_path, source, {"crop_keys": [[0.0, 0.3]], "crop_manual": True})
    assert not called and res2["tracking"]["source"] == "manual"


@needs_ffmpeg
def test_shot_framing_survives_silence_cut_and_keeps_audio(tmp_path, source, monkeypatch):
    monkeypatch.setattr(shots, "plan", lambda *a, **k: PLAN)
    res = run(tmp_path, source, cut=True)
    out = media.probe(tmp_path / res["file"])
    assert res["framing"] == "shots" and out.has_audio and out.duration == pytest.approx(res["duration"], abs=0.3)


@needs_ffmpeg
def test_shot_framing_can_be_turned_off_and_failure_falls_back(tmp_path, source, monkeypatch):
    monkeypatch.setattr(shots, "plan", lambda *a, **k: PLAN)
    off = run(tmp_path, source, cfg_extra={"shot_framing": False})
    assert off["framing"] == "tracking"
    def boom(*a, **k):
        raise RuntimeError("detektor rusak")
    monkeypatch.setattr(shots, "plan", boom)
    fb = run(tmp_path, source)
    assert fb["framing"] == "tracking" and (tmp_path / fb["file"]).is_file()
