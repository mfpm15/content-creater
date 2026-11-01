import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clipper import delivery, project
from clipper.config import FFMPEG
from clipper.server import app

GOOD = {"duration": 45, "width": 1080, "height": 1920, "fps": 30, "has_audio": True, "lufs": -14.5}


def codes(r):
    return {i["code"] for i in r["issues"]}


def test_good_clip_passes_every_platform():
    for pid in delivery.PLATFORMS:
        assert delivery.evaluate(GOOD, pid) == {**delivery.evaluate(GOOD, pid), "ok": True, "issues": []}


def test_aliases_and_unknown_platform():
    assert delivery.platform_id("YouTube") == "shorts"
    assert delivery.platform_id("ig") == "reels"
    with pytest.raises(ValueError):
        delivery.platform_id("myspace")


def test_duration_limit_differs_per_platform():
    long = {**GOOD, "duration": 240}
    assert delivery.evaluate(long, "tiktok")["ok"]
    r = delivery.evaluate(long, "shorts")
    assert not r["ok"] and "duration" in codes(r)
    mid = {**GOOD, "duration": 120}
    assert delivery.evaluate(mid, "shorts")["ok"]
    assert not delivery.evaluate(mid, "reels")["ok"]


def test_allowed_aspects_differ_per_platform():
    four_five = {**GOOD, "width": 1080, "height": 1350}
    assert delivery.evaluate(four_five, "reels")["ok"]
    assert "aspect" in codes(delivery.evaluate(four_five, "tiktok"))
    assert delivery.evaluate({**GOOD, "width": 1080, "height": 1080}, "tiktok")["ok"]


def test_landscape_and_missing_audio_are_errors():
    r = delivery.evaluate({**GOOD, "width": 1920, "height": 1080, "has_audio": False}, "reels")
    assert not r["ok"] and {"aspect", "no-audio"} <= codes(r)


def test_loudness_and_low_resolution_only_warn():
    r = delivery.evaluate({**GOOD, "width": 720, "height": 1280, "lufs": -24.0}, "tiktok")
    assert r["ok"] and {"loudness", "resolution"} <= codes(r)
    assert "resolution" not in codes(delivery.evaluate(GOOD, "tiktok"))
    low = delivery.evaluate({**GOOD, "width": 540, "height": 960}, "tiktok")
    assert low["ok"] and "resolution" in codes(low)


def test_cinema_fps_is_fine_and_only_above_60_fails():
    # 23,98 fps adalah frame rate sinema normal (video WIRED uji): bukan masalah.
    assert delivery.evaluate({**GOOD, "fps": 23.98}, "tiktok")["issues"] == []
    assert delivery.evaluate({**GOOD, "fps": 60}, "tiktok")["ok"]
    r = delivery.evaluate({**GOOD, "fps": 120}, "tiktok")
    assert not r["ok"] and "fps" in codes(r)


def test_unmeasured_loudness_warns_not_fails():
    r = delivery.evaluate({**GOOD, "lufs": None}, "tiktok")
    assert r["ok"] and "loudness-unmeasured" in codes(r)


@pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")
def test_check_measures_real_file(tmp_path):
    f = tmp_path / "c.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=3",
                    "-f", "lavfi", "-i", "sine=f=440:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
    r = delivery.check(f, "tiktok")
    assert r["ok"] and r["measured"]["height"] == 1920
    assert isinstance(r["measured"]["lufs"], float)
    assert set(delivery.check_all(f)) == set(delivery.PLATFORMS)


@pytest.mark.skipif(not (shutil.which(FFMPEG) or Path(FFMPEG).exists()), reason="ffmpeg tidak tersedia")
def test_delivery_endpoint_status_codes():
    p = project.create("/nonexistent.mp4", {})
    project.cancel(p["id"])
    try:
        f = project.pdir(p["id"]) / "clip_01.mp4"
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
                        "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(f)], check=True)
        with project._LOCK:
            q = project.load(p["id"])
            q["candidates"] = q["clips"] = [
                {"id": "clip_01", "start": 0, "end": 2, "status": "done", "file": "clip_01.mp4", "title": "t"},
                {"id": "clip_02", "start": 0, "end": 2, "status": "queued", "title": "t"}]
            project.save(q)
        base = f"/api/projects/{p['id']}/clips"
        with TestClient(app) as c:
            r = c.get(f"{base}/clip_01/delivery")
            assert r.status_code == 200 and set(r.json()) == set(delivery.PLATFORMS)
            r = c.get(f"{base}/clip_01/delivery?platform=youtube")
            assert r.status_code == 200 and r.json()["platform"] == "shorts" and r.json()["ok"]
            assert c.get(f"{base}/clip_01/delivery?platform=myspace").status_code == 400
            assert c.get(f"{base}/clip_02/delivery").status_code == 409
            assert c.get(f"{base}/nope/delivery").status_code == 404
    finally:
        project.delete(p["id"])
