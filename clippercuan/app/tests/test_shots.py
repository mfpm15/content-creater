"""Framing per-shot: batas shot, klasifikasi (satu wajah / dua wajah / B-roll), irisan potong jeda, filtergraph."""
import pytest

from clipper import facetrack, render, shots
from clipper.config import DEFAULTS, deep_merge
from clipper.media import Probe

FPS = facetrack.SAMPLE_FPS


def frame(*boxes, motion=None):
    """boxes: (cx, cy, w, h) pecahan frame."""
    return {"faces": [(b[0], b[2], 0.0) for b in boxes], "motion": motion, "boxes": list(boxes)}


def seconds(n, *boxes):
    return [frame(*boxes) for _ in range(int(n * FPS))]


def test_boundaries_cover_clip_without_gaps_and_merge_tiny_shots():
    b = shots.boundaries([5.0, 5.1, 12.0], 20.0)
    assert b[0][0] == 0.0 and b[-1][1] == 20.0
    assert all(abs(x[1] - y[0]) < 1e-6 for x, y in zip(b, b[1:]))
    assert (5.0, 5.1) not in b                      # cut 5.1 terlalu dekat → digabung
    assert shots.boundaries([], 7.0) == [(0.0, 7.0)]
    assert shots.boundaries([19.9], 20.0) == [(0.0, 20.0)]   # cut di ujung tidak membuat shot nol
    assert shots.boundaries([3.0], 0) == []


def test_classify_single_face_follows_face_and_zooms_wide_shot():
    info = seconds(4, (0.52, 0.30, 0.07, 0.12))          # wajah kecil (shot lebar, ~7% lebar frame)
    s = shots.classify(info, 0.0, 4.0, 1920, 1080)
    assert s["mode"] == "single" and s["keys"] and 1.5 < s["zoom"] <= shots.MAX_SHOT_ZOOM
    mid = shots.classify(seconds(4, (0.52, 0.30, 0.12, 0.2)), 0.0, 4.0, 1920, 1080)
    assert 1.0 < mid["zoom"] < s["zoom"]                 # makin kecil wajahnya, makin besar zoom-nya
    close = shots.classify(seconds(4, (0.5, 0.35, 0.30, 0.55)), 0.0, 4.0, 1920, 1080)
    assert close["mode"] == "single" and close["zoom"] == 1.0       # sudah dekat: tidak di-zoom lagi


def test_classify_two_faces_together_is_multi_with_left_to_right_order():
    info = seconds(4, (0.75, 0.4, 0.14, 0.25), (0.25, 0.4, 0.15, 0.26))   # urutan deteksi acak
    s = shots.classify(info, 0.0, 4.0, 1920, 1080)
    assert s["mode"] == "multi"
    assert s["faces"][0][0] < s["faces"][1][0], "panel atas = orang kiri, bawah = orang kanan"


def test_alternating_single_speakers_are_never_multi():
    # Podcast hasil edit: A lalu B, tidak pernah bersama dalam satu bingkai.
    a = shots.classify(seconds(3, (0.3, 0.4, 0.2, 0.35)), 0.0, 3.0, 1920, 1080)
    b = shots.classify(seconds(3, (0.7, 0.4, 0.2, 0.35)), 0.0, 3.0, 1920, 1080)
    assert a["mode"] == b["mode"] == "single"


def test_no_face_is_broll_and_tiny_faces_are_ignored():
    assert shots.classify([frame() for _ in range(12)], 0.0, 3.0, 1920, 1080)["mode"] == "broll"
    tiny = shots.classify(seconds(3, (0.5, 0.5, 0.02, 0.03), (0.2, 0.5, 0.02, 0.03)), 0.0, 3.0, 1920, 1080)
    assert tiny["mode"] != "multi"


def test_classify_shot_shorter_than_one_sample_does_not_crash():
    info = seconds(2, (0.5, 0.4, 0.2, 0.3))
    assert shots.classify(info, 0.30, 0.40, 1920, 1080)["mode"] == "single"
    assert shots.classify([], 0.0, 1.0, 1920, 1080)["mode"] == "broll"


def test_pieces_keep_total_duration_and_shift_keys_after_silence_cut():
    plan = [{"a": 0.0, "b": 4.0, "mode": "single", "keys": [[0.0, 0.3], [2.0, 0.7]], "zoom": 1.0, "cy": .4},
            {"a": 4.0, "b": 8.0, "mode": "broll", "confidence": .8}]
    keep = [(0.0, 1.0), (1.5, 5.0), (6.0, 8.0)]
    pcs = shots.pieces(plan["shots"] if isinstance(plan, dict) else plan, keep)
    total = sum(p["b"] - p["a"] for p in pcs)
    assert total == pytest.approx(sum(b - a for a, b in keep), abs=1e-6)
    assert all(p["b"] > p["a"] for p in pcs)
    cut = next(p for p in pcs if p["mode"] == "single" and p["a"] == 1.5)
    assert cut["keys"][0][0] == 0.0 and cut["keys"][0][1] == pytest.approx(0.3)   # keyframe digeser ke awal irisan


def test_pieces_merge_slivers_instead_of_dropping_them():
    plan = [{"a": 0.0, "b": 2.0, "mode": "single", "keys": [[0.0, .5]]}, {"a": 2.0, "b": 4.0, "mode": "broll"}]
    pcs = shots.pieces(plan, [(0.0, 1.95), (1.99, 4.0)])
    assert sum(p["b"] - p["a"] for p in pcs) == pytest.approx(1.95 + 2.01, abs=1e-6)
    assert all(p["b"] - p["a"] >= shots.MIN_PIECE - 1e-6 for p in pcs)


def test_shot_graph_covers_every_mode_and_ends_with_fr():
    pr = Probe(60, 1920, 1080, 24, True)
    cfg = deep_merge(DEFAULTS, {"quality": {"sharpen": False}})
    pcs = [{"a": 0, "b": 3, "mode": "single", "keys": [[0.0, .5]], "zoom": 1.8, "cy": .35},
           {"a": 3, "b": 5, "mode": "broll"},
           {"a": 5, "b": 9, "mode": "multi", "faces": [[.25, .4, .15, .26], [.75, .4, .14, .25]]}]
    g = render.shot_graph(pcs, pr, cfg)
    assert g.startswith("[0:v]split=3") and g.count("trim=start=") == 3
    assert "vstack" in g and "boxblur" in g and g.endswith("concat=n=3:v=1:a=0[fr]")
    one = render.shot_graph(pcs[:1], pr, cfg)
    assert "[0:v]null[s0]" in one and one.endswith("[p0]null[fr]")


def test_shot_graph_panel_crops_stay_inside_frame():
    for face in ([.05, .4, .12, .2], [.95, .4, .12, .2], [.5, .02, .3, .4], [.5, .98, .3, .4]):
        cw, ch, x, y = render._panel_rect(face, 1920, 1080, 1080 / 960)
        assert cw % 2 == ch % 2 == 0 and 0 <= x <= 1920 - cw and 0 <= y <= 1080 - ch


def test_adaptive_split_alternating_podcast_is_not_split_but_together_is():
    faces = [{"rect": [0.05, 0.05, 0.42, 0.78], "center": [.26, .3], "hits": 9, "confidence": .8},
             {"rect": [0.53, 0.05, 0.42, 0.78], "center": [.74, .3], "hits": 8, "confidence": .72}]
    alternating = facetrack.adaptive_split("podcast", {"faces": faces, "together": 0.0})
    assert not alternating["enabled"] and "bergantian" in alternating["reason"]
    together = facetrack.adaptive_split("podcast", {"faces": faces, "together": 0.8})
    assert together["enabled"] and together["strategy"] == "dual-speaker"
    legacy = facetrack.adaptive_split("podcast", {"faces": faces})        # proyek lama tanpa field 'together'
    assert legacy["enabled"]
