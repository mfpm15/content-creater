"""Candidate engine contracts: profiles, scoring, diversity, snapping, and determinism."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipper import candidates  # noqa: E402


def sample(index: int, text: str, start: float | None = None) -> dict:
    start = float(index * 40 if start is None else start)
    return {
        "id": f"c{index}", "start": start, "end": start + 30, "text": text,
        "title": text[:30], "confidence": .9,
        "breakdown": {"hook": 60 + index, "clarity": 80, "payoff": 85, "novelty": 70,
                      "emotional_shift": 55, "quotability": 65, "information_density": 75,
                      "visual_action": 45, "clean_ending": 90, "profile_fit": 80,
                      "transcript_confidence": 90, "crop_confidence": 75, "rights_context_risk": 10},
    }


def test_profile_classifier_and_override_profiles():
    tech = {"segments": [{"text": "Review kamera, baterai, fitur, harga, dan performa produk."}]}
    game = {"segments": [{"text": "MLBB lord turtle jungler savage dan turret."}]}
    podcast = {"segments": [{"text": "Host podcast bertanya kenapa narasumber punya cerita ini."}]}
    assert candidates.classify_profile(tech)["profile"] == "tech_review"
    assert candidates.classify_profile(game)["profile"] == "mobile_legends"
    assert candidates.classify_profile(podcast)["profile"] == "podcast"
    assert {"general", "podcast", "interview", "review", "tech_review",
            "gaming", "mobile_legends", "educational"} <= set(candidates.PROFILES)


def test_profile_weights_change_score_without_mutation():
    breakdown = {key: 50 for key in candidates.DIMENSIONS}
    breakdown["visual_activity"] = 100
    breakdown["information_density"] = 10
    game = candidates.weighted_score(breakdown, "mobile_legends")
    tech = candidates.weighted_score(breakdown, "tech_review")
    assert game > tech and breakdown["visual_activity"] == 100


def test_chunk_ranges_have_controlled_overlap():
    chunks = candidates.chunk_ranges(2000, 900, 30)
    assert chunks == [(0.0, 900), (870, 1770), (1740, 2000)]
    assert chunks[0][1] - chunks[1][0] == 30


def test_boundary_snapping_is_sentence_aware():
    segments = [{"s": 0, "e": 4}, {"s": 4.2, "e": 9.8}, {"s": 10, "e": 15}]
    assert candidates.snap_boundary(3.8, 10.2, segments) == (4.2, 9.8)


def test_overlap_suppression_and_semantic_diversity():
    items = [sample(1, "kamera baterai bagus"), sample(2, "kamera baterai bagus", 80),
             sample(3, "harga murah untuk pelajar"), sample(4, "gaming performa tinggi")]
    ranked = candidates.rerank(items, "tech_review", diversity=.6, max_overlap=.2)
    assert len(ranked) == 4
    assert ranked[1]["text"] != ranked[0]["text"]
    overlapping = [sample(1, "satu", 0), sample(2, "dua", 5)]
    assert len(candidates.rerank(overlapping, "podcast", max_overlap=.2)) == 1


def test_ranking_determinism_and_goal_lists():
    items = [sample(i, f"topik unik {i}") for i in range(1, 6)]
    first = candidates.rerank(items, "podcast")
    second = candidates.rerank(list(reversed(items)), "podcast")
    assert [x["id"] for x in first] == [x["id"] for x in second]
    goals = candidates.rankings(first)
    assert set(goals) == set(candidates.GOALS)
    assert all(len(value) == len(first) for value in goals.values())


def test_pin_ban_and_rights_manifest():
    pinned, banned = sample(1, "pin"), sample(2, "ban")
    pinned["pinned"] = True; banned["banned"] = True
    ranked = candidates.rerank([banned, pinned, sample(3, "normal")], "podcast")
    assert ranked[0]["id"] == "c1" and all(x["id"] != "c2" for x in ranked)
    data = candidates.manifest(ranked, "podcast", "local.mp4")
    assert data["schema_version"] == candidates.SCHEMA_VERSION
    assert data["rights_checklist"]["source_permission"] is False
    assert "bukan nasihat hukum" in data["rights_checklist"]["note"]
