"""Video panel/panggung (>=2 orang sebanding di satu frame) tidak boleh dianggap gameplay + facecam.

Kasus nyata: panel Huang & Musk (3 orang di panggung, 2560x1440) diklasifikasi 'mobile_legends' lalu di-split gaming.
"""
import numpy as np

from clipper import facetrack, project


def fake_detector(per_frame):
    """Ganti _Detector dengan deteksi terjadwal: per_frame = list daftar (x, y, w, h) pada kanvas 960 lebar."""
    it = iter(per_frame)

    class D:
        yunet = None

        def __init__(self, *a):
            pass

        def __call__(self, gray):
            return [(x, y, w, h, None) for x, y, w, h in next(it)]
    return D


def frames(n):
    return [np.zeros((540, 960), np.uint8) for _ in range(n)]


def test_two_similar_faces_in_frame_is_multi_person(monkeypatch):
    two = [(100, 60, 120, 140), (700, 80, 110, 130)]
    monkeypatch.setattr(facetrack, "_Detector", fake_detector([two] * 6))
    assert facetrack.multi_person_frames(frames(6)) == 1.0


def test_streamer_facecam_is_not_multi_person(monkeypatch):
    # satu wajah kecil (facecam) + wajah karakter game jauh lebih kecil/tak sebanding
    facecam = [(20, 20, 140, 160)]
    monkeypatch.setattr(facetrack, "_Detector", fake_detector([facecam] * 6))
    assert facetrack.multi_person_frames(frames(6)) == 0.0
    tiny_plus_big = [(20, 20, 140, 160), (500, 300, 30, 36)]       # wajah kedua < 50% lebar yang pertama
    monkeypatch.setattr(facetrack, "_Detector", fake_detector([tiny_plus_big] * 6))
    assert facetrack.multi_person_frames(frames(6)) == 0.0


def test_empty_and_detector_failure_are_safe(monkeypatch):
    assert facetrack.multi_person_frames([]) == 0.0
    class Boom:
        def __init__(self, *a):
            raise RuntimeError("tidak ada detektor")
    monkeypatch.setattr(facetrack, "_Detector", Boom)
    assert facetrack.multi_person_frames(frames(3)) == 0.0


def test_activity_rejects_corner_facecam_when_scene_has_several_people(monkeypatch, tmp_path):
    from clipper import media
    cam = {"rect": [0.08, 0.0, 0.28, 0.39], "big_face": False, "hits": 8}
    comp = {"faces": [{"rect": [.1, .05, .24, .42], "center": [.23, .2], "hits": 8, "confidence": .67}], "confidence": .67, "samples": 12}
    saved = {}
    monkeypatch.setattr(project, "_sample_frames", lambda *a, **k: frames(12))
    monkeypatch.setattr(facetrack, "detect_facecam", lambda fr: dict(cam))
    monkeypatch.setattr(facetrack, "detect_composition", lambda fr: dict(comp))
    monkeypatch.setattr(project, "update", lambda pid, **kw: saved.update(kw))
    monkeypatch.setattr(facetrack, "multi_person_frames", lambda fr, **k: 0.67)
    pr = media.Probe(1650, 2560, 1440, 30, True)
    act = project._activity({"id": "x"}, pr, tmp_path / "s.mkv", {"words": [{"w": "a", "s": 0, "e": 1}] * 50, "segments": []},
                            {"content_profile": "auto", "split": {"auto": True}})
    assert act["gameplay"] is False and act["facecam"] is None
    assert saved["facecam"]["rejected"] == "multi-person-scene" and saved["visual_composition"]["multi_person"] == 0.67

    monkeypatch.setattr(facetrack, "multi_person_frames", lambda fr, **k: 0.0)     # facecam streamer sungguhan tetap dikenali
    act = project._activity({"id": "x"}, pr, tmp_path / "s.mkv", {"words": [], "segments": []},
                            {"content_profile": "auto", "split": {"auto": True}})
    assert act["gameplay"] is True and act["facecam"] == cam["rect"]


def test_general_profile_with_several_stable_faces_does_not_lock_a_static_panel():
    faces = [{"rect": [.1, .05, .24, .42], "center": [.23, .2], "hits": 8, "confidence": .67},
             {"rect": [.66, .13, .24, .40], "center": [.78, .29], "hits": 7, "confidence": .58}]
    d = facetrack.adaptive_split("general", {"faces": faces, "confidence": .67, "together": .67}, {})
    assert d["enabled"] is False and d["fallback"] == "portrait"
    d = facetrack.adaptive_split("general", {"faces": faces[:1], "confidence": .67, "together": 0}, {})
    assert d["enabled"] is True      # satu presenter stabil: perilaku lama

