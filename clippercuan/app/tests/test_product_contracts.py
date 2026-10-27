"""Product contracts for ID/EN subtitles, profiles, recipes, and API parity."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from clipper import asr, candidates, profiles, recipes  # noqa: E402
from clipper.server import app  # noqa: E402


def _words(text: str, confidence: float = .92) -> list[dict]:
    return [{"w": token, "s": i * .4, "e": i * .4 + .34, "p": confidence}
            for i, token in enumerate(text.split())]


def test_profile_registry_is_single_complete_source_of_truth():
    expected = {"general", "podcast", "interview", "review", "tech_review",
                "gaming", "mobile_legends", "educational"}
    assert expected <= set(profiles.REGISTRY)
    assert candidates.PROFILES is profiles.REGISTRY
    for profile_id in expected:
        resolved = profiles.resolve(profile_id)
        assert resolved["id"] == profile_id
        assert resolved["duration"][0] < resolved["duration"][1]
        assert resolved["recipe"] in recipes.RECIPES
        assert resolved["crop_strategy"]
        assert resolved["caption_policy"]
        assert resolved["safe_zones"]
        assert resolved["speaker_policy"]
        assert resolved["weights"]


def test_profile_payloads_change_pipeline_substantively():
    podcast = profiles.resolve("podcast")
    review = profiles.resolve("review")
    gaming = profiles.resolve("gaming")
    education = profiles.resolve("educational")
    assert podcast["recipe"] != review["recipe"]
    assert podcast["crop_strategy"] != gaming["crop_strategy"]
    assert review["safe_zones"] != education["safe_zones"]
    assert podcast["speaker_policy"] != review["speaker_policy"]
    assert gaming["weights"] != education["weights"]


def test_profile_api_and_preview_return_resolved_reasons():
    with TestClient(app) as client:
        response = client.get("/api/profiles")
        assert response.status_code == 200
        body = response.json()
        assert body["source_of_truth"] == "backend"
        assert len(body["profiles"]) >= 8
        preview = client.post("/api/profiles/preview", json={
            "profile": "review", "classification_confidence": .91,
            "evidence": ["produk", "perbandingan", "harga"],
        })
        assert preview.status_code == 200
        data = preview.json()
        assert data["resolved"]["id"] == "review"
        assert data["resolved"]["recipe"] == "box-punch-review"
        assert data["reasons"] and data["confidence"] == .91


def test_auto_profile_low_confidence_falls_back_to_general_clean_large():
    resolved = profiles.resolve_selection("auto", {
        "profile": "gaming", "confidence": .35, "evidence": ["visual activity"],
    })
    assert resolved["id"] == "general"
    assert resolved["recipe"] == "recommended"
    assert resolved["fallback"] is True
    assert "confidence" in resolved["reason"].lower()


def test_transcript_contract_id_en_and_code_switching():
    words = _words("Kita review Microsoft Copilot dan battery life hari ini")
    result = asr.finalize_transcript(
        words, requested_language="auto", detected_language="id",
        backend="whisper-local", model="small", language_confidence=.88,
        timing_source="word", fallback_reason=None,
    )
    required = {"requested_language", "detected_language", "language_confidence",
                "code_switching", "asr_backend", "asr_model", "word_timestamps",
                "normalization_profile", "cleanup_edits", "segmentation_metrics",
                "caption_layer_count", "render_allowed", "status"}
    assert required <= set(result)
    assert result["requested_language"] == "auto"
    assert result["detected_language"] == "id"
    assert result["code_switching"]["detected"] is True
    assert {"Microsoft", "Copilot"} <= {word["w"] for word in result["words"]}
    assert result["caption_layer_count"] == 1
    assert result["render_allowed"] is True


def test_english_contractions_and_indonesian_slang_preserved():
    en = asr.finalize_transcript(
        _words("I don't think it's broken"), "en", "en", "fixture", "fixture-en", .96, "word", None,
    )
    mixed = asr.finalize_transcript(
        _words("Gue nggak mau translate nama OpenAI"), "id", "id", "fixture", "fixture-id", .94, "word", None,
    )
    assert "don't" in [word["w"].lower() for word in en["words"]]
    assert "it's" in [word["w"].lower() for word in en["words"]]
    assert "nggak" in [word["w"].lower() for word in mixed["words"]]
    assert "OpenAI" in [word["w"] for word in mixed["words"]]


def test_low_confidence_and_no_audio_never_fabricate_subtitles():
    low = asr.finalize_transcript(
        _words("uncertain words", .2), "auto", "en", "fixture", "fixture-low", .31, "word", "low confidence",
    )
    silent = asr.finalize_transcript(
        [], "auto", None, "fixture", "fixture-silent", 0.0, "none", "no audio",
    )
    for result in (low, silent):
        assert result["render_allowed"] is False
        assert result["status"] == "needs_attention"
        assert result["warning"]
        assert set(result["retry_options"]) >= {"model", "language_override", "backend"}


def test_recipe_catalog_has_four_primary_recommendations_and_compat_aliases():
    public = recipes.public()
    primary = [entry for entry in public.values() if entry.get("surface") == "primary"]
    assert len(primary) <= 4
    assert {entry["category"] for entry in primary} == {"Bersih", "Dinamis", "Edukasi", "Gaming"}
    assert {entry["id"] for entry in primary} == {
        "recommended", "box-punch-podcast", "clean-focus", "ml-hype",
    }
    assert all("viral" not in (entry.get("label", "") + entry.get("desc", "")).lower() for entry in primary)
    assert recipes.resolve_id("podcast-hormozi") in recipes.RECIPES
    assert public["podcast-hormozi"]["surface"] == "experimental"


def test_recipe_preview_uses_renderer_object():
    preview = recipes.preview("box-punch-review", "review")
    renderer = recipes.resolve("box-punch-review", "review")["settings"]
    assert preview["renderer_settings"] == renderer
    assert preview["caption"] == renderer["caption"]
    assert preview["crop_strategy"]
    assert preview["safe_zones"]
    assert preview["changes"]
