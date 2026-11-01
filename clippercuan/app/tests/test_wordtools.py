"""Alat kualitas transkrip + ekspor subtitle + pratinjau potong jeda (ide dawn-cut / SubtitleEdit / tscaps)."""
import json

import pytest
from fastapi.testclient import TestClient

from clipper import project, wordtools
from clipper.server import app


def W(text, step=.4, p=.9, start=0.0, gaps=None):
    gaps, out, t = gaps or {}, [], start
    for i, w in enumerate(text.split()):
        out.append({"w": w, "s": round(t, 3), "e": round(t + step * .85, 3), "p": p})
        t += step + gaps.get(i, 0)
    return out


def test_filler_repeat_and_low_confidence_are_detected_but_nothing_removed():
    ws = W("jadi eh ini ini itu anu bagus")
    ws[6]["p"] = .3
    ws[0]["p"] = None
    r = wordtools.analyze(ws)
    assert [x["w"] for x in r["fillers"]] == ["eh", "anu"]
    assert [x["i"] for x in r["repeats"]] == [3]
    assert [x["w"] for x in r["low_confidence"]] == ["bagus"] and r["low_confidence"][0]["p"] == .3
    assert r["words"] == len(ws) == 7 and "Tidak ada kata yang dihapus" in r["note"]


def test_filler_matching_is_exact_not_substring_and_ignores_punctuation():
    r = wordtools.analyze(W("Umur emas, anuan hmm! em"))
    assert [x["w"] for x in r["fillers"]] == ["hmm!", "em"]      # "Umur" / "emas," / "anuan" bukan filler


def test_low_confidence_skips_when_no_probability_available():
    r = wordtools.analyze([{"w": "a", "s": 0, "e": .2}, {"w": "b", "s": .3, "e": .5}])
    assert r["low_confidence"] == [] and r["has_probability"] is False


def test_clip_words_with_p_uses_transcript_probability_and_relative_time():
    tw = W("satu dua tiga empat lima", start=10.0, p=.8)
    tw[2]["p"] = .2
    out = wordtools.clip_words_with_p(tw, {"start": 10.0, "end": 12.0})
    assert out[0]["s"] == 0.0 and out[2]["p"] == .2 and all(w["s"] < 2.3 for w in out)


def test_silence_preview_reports_saved_time_and_cuts():
    ws = W("satu dua", gaps={1: 3.0}) + W("tiga empat", start=4.0)
    r = wordtools.silence_preview(ws, 6.0)
    assert r["segments"] == 2 and r["saved"] > 1.5 and r["result"] + r["saved"] == pytest.approx(r["original"], abs=.02)
    assert any(c["dur"] > 1.5 for c in r["cuts"])


def test_silence_preview_without_gaps_saves_nothing_significant():
    r = wordtools.silence_preview(W("a b c d e f", step=.3), 1.9)
    assert r["segments"] == 1 and r["saved"] < .6


def test_timeline_words_follow_cut_silence_only_when_enabled():
    ws = W("satu dua", gaps={1: 3.0}) + W("tiga empat", start=4.0)
    same = wordtools.timeline_words(ws, 6.0, {"cut_silence": False})
    cut = wordtools.timeline_words(ws, 6.0, {"cut_silence": True, "silence_gap": .55})
    assert same == ws and cut[2]["s"] < ws[2]["s"] - 1.5


@pytest.mark.parametrize("fmt", ["srt", "vtt", "sbv", "ass", "txt"])
def test_every_export_format_keeps_all_words_in_order(fmt):
    ws = W("ini kalimat pertama. ini kalimat kedua yang lebih panjang lagi ya")
    out = wordtools.export_subtitles(ws, fmt, 4)
    flat = " ".join(out.split())
    for w in ws:
        assert w["w"] in flat
    assert flat.index("pertama.") < flat.index("kedua")


def test_srt_vtt_sbv_timestamp_shapes():
    ws = W("halo dunia ini tes")
    assert "00:00:00,000 --> " in wordtools.export_subtitles(ws, "srt")
    v = wordtools.export_subtitles(ws, "vtt")
    assert v.startswith("WEBVTT") and "00:00:00.000 --> " in v
    assert wordtools.export_subtitles(ws, "sbv").splitlines()[0].startswith("0:00:00.000,0:00:")


def test_word_timing_adds_karaoke_tags():
    ws = W("halo dunia ini tes")
    assert "{\\k" in wordtools.export_subtitles(ws, "ass", word_timing=True)
    assert "<00:00:" in wordtools.export_subtitles(ws, "vtt", word_timing=True)
    assert "{\\k" not in wordtools.export_subtitles(ws, "ass", word_timing=False)


def test_unknown_format_raises_clear_error():
    with pytest.raises(ValueError, match="Format tidak dikenal"):
        wordtools.export_subtitles(W("a b"), "docx")


@pytest.fixture()
def seeded():
    p = project.create("/nonexistent.mp4", {})
    project.cancel(p["id"])
    words = W("jadi eh ini bagus sekali", start=5.0)
    words[4]["p"] = .3
    pd = project.pdir(p["id"])
    (pd / "transcript.json").write_text(json.dumps({"words": words, "segments": []}), "utf-8")
    with project._LOCK:
        q = project.load(p["id"])
        q["candidates"] = q["clips"] = [{"id": "clip_01", "start": 5.0, "end": 8.0, "status": "queued", "title": "t"}]
        project.save(q)
    yield p["id"]
    project.delete(p["id"])


def test_quality_endpoint(seeded):
    with TestClient(app) as c:
        r = c.get(f"/api/projects/{seeded}/clips/clip_01/quality")
        assert r.status_code == 200
        q = r.json()
        assert [x["w"] for x in q["quality"]["fillers"]] == ["eh"]
        assert q["quality"]["low_confidence"][0]["w"] == "sekali"
        assert q["silence"]["original"] == 3.0
        assert c.get(f"/api/projects/{seeded}/clips/nope/quality").status_code == 404


def test_quality_endpoint_handles_legacy_clip_without_timing(seeded):
    with project._LOCK:
        q = project.load(seeded)
        q["clips"].append({"id": "legacy", "status": "queued", "title": "data lama"})
        project.save(q)
    with TestClient(app) as c:
        r = c.get(f"/api/projects/{seeded}/clips/legacy/quality")
        assert r.status_code == 409
        assert "waktu mulai/akhir" in r.json()["detail"]


def test_subtitles_endpoint_formats_and_errors(seeded):
    with TestClient(app) as c:
        for fmt, marker in (("srt", "-->"), ("vtt", "WEBVTT"), ("ass", "[Events]"), ("txt", "jadi"), ("sbv", ",")):
            r = c.get(f"/api/projects/{seeded}/clips/clip_01/subtitles?format={fmt}")
            assert r.status_code == 200 and marker in r.text and "attachment" in r.headers["content-disposition"]
        assert c.get(f"/api/projects/{seeded}/clips/clip_01/subtitles?format=docx").status_code == 400
        assert c.get(f"/api/projects/{seeded}/clips/zzz/subtitles").status_code == 404
