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


def test_tech_review_default_is_clean_large_single_caption():
    rid = recipes.PROFILE_DEFAULT["tech_review"]
    recipe = recipes.RECIPES[rid]
    cap = recipe["settings"]["caption"]
    assert rid == "recommended" and recipe["template_name"] == "Clean Large"
    assert cap["template_id"] == "clean-large" and cap["size_level"] == "large"
    assert cap["style"] == "clean" and cap["box"] is False
    assert cap["animation"] == "none" and cap["effect"] == "none"
    assert recipe["settings"]["title"]["enabled"] is False
    assert recipe["settings"]["caption_layers"] == 1
    assert cap["size"] == recipes.CAPTION_SIZE_LEVELS["large"] > recipes.CAPTION_SIZE_LEVELS["medium"]
    assert cap["max_lines"] == 2 and cap["line_height"] >= 1.1
    assert cap["outline"] >= 4 and 3 <= cap["words_per_line"] <= 6


def test_clean_ass_uses_configured_thin_outline_without_shadow():
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "clean", "outline": 3, "shadow": 0}})
    ass = captions.build_ass(_words("caption bersih tidak boleh memiliki outline tebal"), "", cfg, (1080, 1920), 8)
    cap_style = next(line for line in ass.splitlines() if line.startswith("Style: Cap,"))
    fields = cap_style.split(",")
    assert fields[16] == "3"
    assert fields[17] == "0"


def test_render_exports_sidecars_outside_mp4_directory_basename_contract():
    source = Path(render.__file__).read_text("utf-8")
    assert 'subtitle_dir = work / "subtitles"' in source
    assert '"sidecar_autoload_safe": True' in source
    assert '"srt": f"subtitles/{cid}.srt"' in source
    assert '"ass": f"subtitles/{cid}.ass"' in source


def test_clean_focus_uses_same_font_and_subtle_keyword_scale():
    cfg = deep_merge(DEFAULTS, {"caption": {"style": "keyword", "accent_mode": "color",
                                             "accent_font": "Barlow Condensed", "accent_scale": 108,
                                             "highlight": "#FFD166", "animation": "none", "effect": "none"}})
    ass = captions.build_ass(_words("ini rahasia caption yang tetap bersih"), "", cfg, (1080, 1920), 8)
    dialogue = "\n".join(line for line in ass.splitlines() if line.startswith("Dialogue:"))
    assert "\\fscx108\\fscy108" in dialogue
    assert "\\fscx118" not in dialogue
    assert "\\fnInstrument Serif" not in dialogue
    events = [line for line in dialogue.splitlines() if line]
    assert len(events) == 2
    assert all(line.count(captions._ass_color("#FFD166")) == 1 for line in events)


def test_box_punch_v2_is_opt_in_production_and_keeps_single_layer_contract():
    entry = recipes.RECIPES["box-punch"]
    assert entry["tier"] == "advanced" and entry["experimental"] is False
    assert entry["status"] == "Production"
    recipe = entry["settings"]
    cap = recipe["caption"]
    assert cap["template_id"] == "box-punch-v2"
    assert cap["style"] == "box" and cap["box"] is True
    assert cap["animation"] == "subtle-pop" and cap["animation_ms"] <= 200
    assert cap["effect"] == "none" and cap["max_lines"] == 2
    assert recipe["decoration"]["mode"] == "none"
    assert recipe["caption_layers"] == 1 and recipe["title"]["enabled"] is False


def test_all_primary_templates_have_identity_and_two_line_contract():
    expected = {"recommended": "clean", "clean-focus": "keyword", "minimal-medium": "clean"}
    for rid, style in expected.items():
        recipe = recipes.RECIPES[rid]
        cap = recipe["settings"]["caption"]
        assert recipe["template_name"] and cap["template_id"]
        assert recipe["tier"] == "primary" and recipe["experimental"] is False
        assert cap["max_lines"] == 2 and cap["line_height"] >= 1.1
        assert cap["animation"] == "none" and cap["effect"] == "none"
        assert cap["style"] == style and cap["box"] is False
        assert recipe["settings"]["caption_layers"] == 1


def test_advanced_templates_are_never_automatic():
    automatic = {"recommended", *recipes.PROFILE_DEFAULT.values()}
    for rid in ("viral-pop", "box-punch", "neon-karaoke"):
        recipe = recipes.RECIPES[rid]
        assert rid not in automatic
        assert recipe["tier"] == "advanced"
    assert recipes.RECIPES["box-punch"]["status"] == "Production"
    for rid in ("viral-pop", "neon-karaoke"):
        assert recipes.RECIPES[rid]["experimental"] is True
        assert "Eksperimental" in recipes.RECIPES[rid]["label"]


def test_size_mapping_is_deterministic_and_large_exceeds_medium():
    assert recipes.CAPTION_SIZE_LEVELS == {"small": 64, "medium": 72, "large": 84, "xlarge": 96}
    assert recipes.RECIPES["recommended"]["settings"]["caption"]["size"] > recipes.RECIPES["minimal-medium"]["settings"]["caption"]["size"]


def test_render_manifest_contract_contains_identity_and_effective_metric():
    source = Path(render.__file__).read_text("utf-8")
    for field in ("template_id", "template_name", "effective_caption_height_pct", "caption_render", "animation", "active_word"):
        assert field in source
    assert source.count("ass=filename=") == 1


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


def test_decoration_planner_has_provenance_and_never_overlaps():
    from clipper import effects

    words = _words("uang penting uang")
    planned = effects.plan_emojis(words, 5, min_gap=0, provenance="keyword")
    assert all(item["provenance"] == "keyword" and item["keyword"] for item in planned)
    assert all(a["e"] <= b["s"] for a, b in zip(planned, planned[1:]))


def test_decoration_safe_zone_protects_mobile_legends_hud():
    from clipper import effects

    zones = effects.safe_zones("mobile_legends", "blur", 76)
    assert {z["kind"] for z in zones} >= {"spoken-caption", "minimap", "score", "controls", "kill-feed"}
    decision = effects.decoration_layout("mobile_legends", "blur", 76)
    assert "reason" in decision and "blocked" in decision


def test_review_product_and_podcast_face_safe_zones():
    from clipper import effects

    assert "product" in {z["kind"] for z in effects.safe_zones("tech_review", "portrait")}
    assert "face" in {z["kind"] for z in effects.safe_zones("podcast", "portrait")}


def test_auto_profile_defaults_remain_clean_when_not_gaming():
    for profile in ("podcast", "interview", "tech_review", "review", "educational"):
        assert recipes.PROFILE_DEFAULT[profile] == "recommended"
    cap = recipes.RECIPES["recommended"]["settings"]["caption"]
    assert cap["template_id"] == "clean-large" and cap["animation"] == "none"
