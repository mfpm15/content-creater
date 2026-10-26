"""Contracts for transcript quality, glossary, segmentation, templates, and caption validation."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipper import caption_workspace as cw  # noqa: E402


def words(text: str, synthetic: bool = False) -> list[dict]:
    result = []
    current = 0.0
    for token in text.split():
        item = {"w": token, "s": current, "e": current + 0.32, "p": 0.92}
        if synthetic:
            item["synthetic_timing"] = True
        result.append(item)
        current += 0.4
    return result


def test_quality_report_is_diagnostic_and_source_aware():
    transcript = {"words": words("ini transkrip manual yang cukup jelas"), "source": "youtube-manual", "language": "id"}
    report = cw.quality_report(transcript, 3)
    assert report["kind"] == "diagnostic_not_wer"
    assert report["source"] == "youtube-manual"
    assert 0 <= report["score"] <= 100
    assert report["timing_mode"] == "word"


def test_synthetic_timing_disables_precise_word_mode():
    report = cw.quality_report({"words": words("timing ini hanya estimasi frasa", True), "source": "youtube-auto"}, 3)
    assert report["timing_mode"] == "phrase-estimated"
    assert any("Timing per kata" in warning for warning in report["warnings"])


def test_glossary_only_changes_explicit_variants_and_audits():
    source = words("mobel lejen dan istilah lain")
    changed, audit = cw.apply_glossary(source, [{"canonical": "Mobile Legends", "variants": ["mobel"]}])
    assert changed[0]["w"] == "Mobile Legends"
    assert changed[1]["w"] == "lejen"
    assert audit[0]["before"] == "mobel" and audit[0]["after"] == "Mobile Legends"
    assert source[0]["w"] == "mobel"


def test_segmentation_respects_bounds_and_avoids_final_orphan():
    chunks = cw.segment(words("Harga perangkat ini Rp 5 juta dan baterai 5000 mAh sangat awet sekali"), 5, 28)
    assert chunks
    assert all(chunk for chunk in chunks)
    assert len(chunks[-1]) != 1


def test_seven_reusable_templates_have_required_fields():
    assert len(cw.TEMPLATES) == 7
    required = {"label", "font", "size", "color", "background", "highlight", "position", "animation", "safe_area", "max_words", "max_chars", "style"}
    assert all(required <= set(template) for template in cw.TEMPLATES.values())
    assert {"clean-pro", "bold-viral", "karaoke-focus"} <= set(cw.TEMPLATES)


def test_validation_reports_overlap_speed_lines_and_safe_zone():
    items = [
        {"start": 0, "end": .4, "text": "caption yang sangat panjang dan terlalu cepat untuk dibaca"},
        {"start": .3, "end": 1.0, "text": "baris satu\nbaris dua\nbaris tiga"},
    ]
    result = cw.validate_cues(items, (1080, 1920), .15)
    codes = {warning["code"] for warning in result["warnings"]}
    assert {"too-short", "cps", "overlap", "lines"} <= codes
    assert result["safe_zone"] == {"x": 162, "y": 288, "width": 756, "height": 1344}
    assert result["valid"] is False


def test_atomic_json_leaves_no_partial_file():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "workspace.json"
        cw.atomic_json(path, {"schema_version": 3, "text": "aman"})
        assert json.loads(path.read_text("utf-8"))["text"] == "aman"
        assert not list(path.parent.glob("*.tmp"))


def test_workspace_recommends_non_karaoke_for_estimated_timing():
    transcript = {"words": words("timing estimasi tidak boleh berpura pura presisi", True), "source": "youtube-auto"}
    workspace = cw.workspace(transcript, 4, "mobile_legends")
    assert workspace["recommended_template"] == "clean-pro"
    assert workspace["schema_version"] == 3
