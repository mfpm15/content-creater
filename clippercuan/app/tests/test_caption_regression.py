"""Production regressions: one spoken-caption layer, safe recipes, and role separation."""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipper import caption_workspace, captions, project, recipes, render  # noqa: E402
from clipper.config import DEFAULTS, deep_merge  # noqa: E402


def _words(text: str) -> list[dict]:
    return [{"w": token, "s": i * .45, "e": i * .45 + .38, "provenance": "transcript"}
            for i, token in enumerate(text.split())]


def _events(ass: str) -> list[dict]:
    result = []
    for line in ass.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        result.append({"layer": int(parts[0].split(":", 1)[1]), "start": parts[1], "end": parts[2],
                       "style": parts[3], "text": re.sub(r"\{[^}]*\}", "", parts[9])})
    return result


def test_filter_graph_has_one_subtitle_renderer():
    source = Path(render.__file__).read_text("utf-8")
    assert source.count("ass=filename=") == 1
    assert "drawtext" not in source and "subtitles=" not in source


def test_ass_has_one_spoken_role_and_distinct_hook_area_time():
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "clean", "box": False, "y_pct": 72},
                                "title": {"enabled": True, "preset": "clean", "duration": 3, "role": "hook", "y_pct": 12}})
    ass = captions.build_ass(_words("satu caption utama yang bersih"), "Hook berbeda", cfg, (1080, 1920), 8)
    events = _events(ass)
    spoken = [e for e in events if e["style"] in {"Cap", "CapBox"} and e["layer"] == 1]
    hooks = [e for e in events if e["style"].startswith("Title")]
    assert spoken and hooks
    assert all("Hook berbeda" not in e["text"] for e in spoken)
    assert all(e["end"] <= "0:00:03.00" for e in hooks)
    assert "Role: spoken-caption" in ass and "Role: hook" in ass


def test_cues_deduplicate_identical_overlap_without_dropping_words():
    items = caption_workspace.normalize_cues([
        {"start": 0, "end": 1.5, "text": "kalimat sama", "role": "spoken-caption", "provenance": "transcript"},
        {"start": .2, "end": 1.2, "text": "kalimat sama", "role": "spoken-caption", "provenance": "retry"},
        {"start": 1.1, "end": 2.0, "text": "lanjutan utuh", "role": "spoken-caption", "provenance": "transcript"},
    ])
    assert [c["text"] for c in items].count("kalimat sama") == 1
    assert items[0]["end"] <= items[1]["start"]
    assert "lanjutan utuh" in items[1]["text"]
    assert caption_workspace.validate_cues(items)["valid"]


def test_tech_review_default_is_recommended_clean_single_caption():
    rid = recipes.PROFILE_DEFAULT["tech_review"]
    recipe = recipes.RECIPES[rid]
    assert rid == "recommended"
    assert recipe["settings"]["caption"]["style"] == "clean"
    assert recipe["settings"]["caption"]["box"] is False
    assert recipe["settings"]["title"]["enabled"] is False
    assert recipe["settings"]["caption_layers"] == 1


def test_duo_is_hook_style_not_duplicate_transcript():
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "clean"},
                                "title": {"enabled": True, "preset": "duo", "duration": 3, "role": "hook"}})
    transcript = "ucapan asli tidak boleh menjadi judul kedua"
    ass = captions.build_ass(_words(transcript), "Hook ringkas berbeda", cfg, (1080, 1920), 8)
    events = _events(ass)
    assert sum(e["style"] == "Cap" for e in events) >= 1
    assert not any(transcript in e["text"] for e in events if e["style"].startswith("Title"))
    assert "Role: spoken-caption" in ass and "Role: hook" in ass


def test_retry_preserves_settings_without_adding_layers():
    p = project.create("/nonexistent.mp4", {"recipe": "recommended", "caption_layers": 1,
                                             "caption": {"style": "clean"}})
    project.cancel(p["id"])
    before = project.load(p["id"])["settings"]
    project.retry(p["id"])
    after = project.load(p["id"])["settings"]
    assert after["caption"]["style"] == before["caption"]["style"] == "clean"
    assert after["caption_layers"] == before["caption_layers"] == 1
