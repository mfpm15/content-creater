"""Chapter sumber (yt-dlp): batas klip dirapikan ke batas chapter; tanpa chapter tidak ada perubahan."""
import json

from clipper import candidates, download

CH = [{"s": 0.0, "e": 100.0, "title": "Intro"}, {"s": 100.0, "e": 170.0, "title": "Inti"}]


def test_snaps_to_chapter_edges_when_close_and_in_range():
    m = [{"start": 101.5, "end": 168.0}]
    candidates.snap_chapters(m, CH, 30, 90)
    assert (m[0]["start"], m[0]["end"]) == (100.0, 170.0)
    assert m[0]["chapter"] == "Inti" and m[0]["chapter_snapped"]


def test_no_snap_when_duration_leaves_range_or_far():
    far = [{"start": 110.0, "end": 160.0}]
    candidates.snap_chapters(far, CH, 30, 90)
    assert (far[0]["start"], far[0]["end"]) == (110.0, 160.0) and "chapter_snapped" not in far[0]
    long = [{"start": 99.0, "end": 169.0}]
    candidates.snap_chapters(long, CH, 30, 60)   # 100..170 = 70s > 60 → tidak digeser
    assert (long[0]["start"], long[0]["end"]) == (99.0, 169.0)


def test_write_chapters_roundtrip_and_clears(tmp_path):
    download.write_chapters(tmp_path, [{"start_time": 0, "end_time": 5, "title": "A"}, {"start_time": None, "end_time": 9}])
    assert json.loads((tmp_path / "chapters.json").read_text("utf-8")) == [{"s": 0.0, "e": 5.0, "title": "A"}]
    download.write_chapters(tmp_path, None)
    assert not (tmp_path / "chapters.json").exists()
