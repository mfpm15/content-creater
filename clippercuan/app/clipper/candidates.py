"""Candidate generation, profile classification, transparent scoring, and diversity ranking."""
from __future__ import annotations

import hashlib
import re
from collections import Counter

SCHEMA_VERSION = 2
DIMENSIONS = (
    "hook", "standalone_clarity", "payoff", "novelty", "emotion_humor",
    "quotability", "information_density", "visual_activity", "clean_ending",
    "profile_fit", "transcript_confidence", "crop_confidence", "rights_context_risk",
)

PROFILES = {
    "podcast": {
        "label": "Podcast & wawancara",
        "result": "Hot take utuh, cerita mini, tanya-jawab, dan insight mandiri",
        "duration": (25.0, 60.0), "layout": "portrait", "caption": "clean",
        "crop": "speaker-aware dengan face crop tengah sebagai fallback",
        "pacing": "natural", "safe_area": 0.14,
        "weights": {"hook": 1.15, "standalone_clarity": 1.35, "payoff": 1.25, "novelty": 1.0,
                    "emotion_humor": 1.0, "quotability": 1.2, "information_density": 1.0,
                    "visual_activity": 0.45, "clean_ending": 1.25, "profile_fit": 1.2,
                    "transcript_confidence": 0.8, "crop_confidence": 0.8, "rights_context_risk": -1.0},
        "terms": ("podcast", "host", "narasumber", "wawancara", "menurut", "cerita", "kenapa", "jawab"),
        "warning": "Pastikan kutipan tidak mengubah maksud pembicara dan izin wajah/suara tersedia.",
    },
    "tech_review": {
        "label": "Review teknologi",
        "result": "Masalah-solusi, demo, perbandingan, verdict, dan value dengan konteks",
        "duration": (20.0, 50.0), "layout": "portrait", "caption": "clean",
        "crop": "produk atau demo lebih utama; wajah sebagai fallback", "pacing": "medium",
        "safe_area": 0.13,
        "weights": {"hook": 1.0, "standalone_clarity": 1.3, "payoff": 1.2, "novelty": 1.1,
                    "emotion_humor": 0.55, "quotability": 0.75, "information_density": 1.4,
                    "visual_activity": 1.05, "clean_ending": 1.1, "profile_fit": 1.35,
                    "transcript_confidence": 1.0, "crop_confidence": 0.9, "rights_context_risk": -1.25},
        "terms": ("review", "fitur", "harga", "spesifikasi", "kamera", "baterai", "performa", "produk", "versus", "worth"),
        "warning": "Harga dan spesifikasi harus berasal dari sumber atau transkrip; jangan menambah klaim.",
    },
    "mobile_legends": {
        "label": "Gaming Mobile Legends",
        "result": "Clutch, outplay, team fight, comeback, objective, tip, reaksi, atau funny fail",
        "duration": (15.0, 40.0), "layout": "split", "caption": "bold-viral",
        "crop": "gameplay-safe; facecam opsional dan tidak menutup HUD", "pacing": "fast",
        "safe_area": 0.16,
        "weights": {"hook": 1.0, "standalone_clarity": 0.8, "payoff": 1.2, "novelty": 0.8,
                    "emotion_humor": 1.25, "quotability": 0.6, "information_density": 0.65,
                    "visual_activity": 1.55, "clean_ending": 0.85, "profile_fit": 1.4,
                    "transcript_confidence": 0.45, "crop_confidence": 1.0, "rights_context_risk": -1.0},
        "terms": ("mobile legends", "mlbb", "lord", "turtle", "turret", "jungler", "roamer", "gank", "ulti", "maniac", "savage"),
        "warning": "Event game hanya diberi label bila didukung ucapan atau sinyal visual/audio yang tersedia.",
    },
}

GOALS = {
    "best_overall": "score",
    "strongest_hook": "hook",
    "densest_insight": "information_density",
    "most_emotional": "emotion_humor",
    "easiest_to_understand": "standalone_clarity",
    "series_potential": "series_potential",
}
TOKEN = re.compile(r"[\w']+", re.UNICODE)


def tokens(text: str) -> set[str]:
    return {x.lower() for x in TOKEN.findall(text) if len(x) > 2}


def classify_profile(transcript: dict, metadata: dict | None = None, activity: dict | None = None) -> dict:
    text = " ".join([str((metadata or {}).get("title", ""))] + [s.get("text", "") for s in transcript.get("segments", [])]).lower()
    activity = activity or {}
    scores = {name: sum(text.count(term) for term in data["terms"]) for name, data in PROFILES.items()}
    if activity.get("gameplay"):
        scores["mobile_legends"] += 3
    if activity.get("product_demo"):
        scores["tech_review"] += 2
    if activity.get("speaker_changes", 0) >= 2:
        scores["podcast"] += 2
    ordered = sorted(scores, key=lambda name: (-scores[name], name))
    best, second = ordered[0], ordered[1]
    total = max(1, scores[best] + scores[second])
    confidence = 0.35 if scores[best] == 0 else min(0.98, 0.55 + (scores[best] - scores[second]) / total * 0.4)
    return {"profile": best, "confidence": round(confidence, 3), "signals": scores, "overridable": True}


def profile(name: str) -> dict:
    return PROFILES.get(name if name != "auto" else "podcast", PROFILES["podcast"])


def overlap(a: dict, b: dict) -> float:
    common = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return common / max(0.001, min(a["end"] - a["start"], b["end"] - b["start"]))


def similarity(a: dict, b: dict) -> float:
    ta, tb = tokens(a.get("transcript_excerpt", a.get("text", ""))), tokens(b.get("transcript_excerpt", b.get("text", "")))
    lexical = len(ta & tb) / max(1, len(ta | tb))
    return max(lexical, overlap(a, b))


def weighted_score(breakdown: dict, profile_name: str) -> int:
    weights = profile(profile_name)["weights"]
    positive = sum(max(0.0, weights.get(k, 0)) * float(breakdown.get(k, 0)) for k in DIMENSIONS)
    scale = sum(max(0.0, v) for v in weights.values()) or 1
    risk = abs(min(0.0, weights.get("rights_context_risk", -1))) * float(breakdown.get("rights_context_risk", 0))
    return max(0, min(100, round(positive / scale - risk * 0.25)))


def topic_cluster(text: str) -> str:
    common = Counter(x.lower() for x in TOKEN.findall(text) if len(x) > 4)
    return common.most_common(1)[0][0] if common else "umum"


def normalize(raw: dict, index: int, profile_name: str, source_duration: float) -> dict:
    start = max(0.0, float(raw.get("start", raw.get("s", 0))))
    end = min(source_duration, float(raw.get("end", raw.get("e", source_duration))))
    text = str(raw.get("transcript_excerpt", raw.get("text", ""))).strip()
    old = raw.get("breakdown") or {}
    breakdown = {
        "hook": old.get("hook", 50),
        "standalone_clarity": old.get("standalone_clarity", old.get("clarity", 50)),
        "payoff": old.get("payoff", 50), "novelty": old.get("novelty", 50),
        "emotion_humor": old.get("emotion_humor", old.get("emotional_shift", 40)),
        "quotability": old.get("quotability", 50),
        "information_density": old.get("information_density", 50),
        "visual_activity": old.get("visual_activity", old.get("visual_action", 35)),
        "clean_ending": old.get("clean_ending", 50), "profile_fit": old.get("profile_fit", 60),
        "transcript_confidence": old.get("transcript_confidence", round(float(raw.get("confidence", .6)) * 100)),
        "crop_confidence": old.get("crop_confidence", 50),
        "rights_context_risk": old.get("rights_context_risk", 15),
    }
    breakdown = {k: max(0, min(100, round(float(v)))) for k, v in breakdown.items()}
    digest = hashlib.sha1(f"{start:.2f}:{end:.2f}:{text}".encode()).hexdigest()[:12]
    score = weighted_score(breakdown, profile_name)
    warnings = list(dict.fromkeys(raw.get("warnings", [])))
    if breakdown["rights_context_risk"] >= 50:
        warnings.append("Periksa hak sumber dan konteks sebelum publikasi")
    if breakdown["transcript_confidence"] < 70:
        warnings.append("Confidence transkrip rendah")
    extras = {k: v for k, v in raw.items() if k not in {"s", "e", "seg0", "seg1"}}  # hasil render/edit tidak boleh hilang saat rerank
    return {
        **extras,
        "id": raw.get("id") or f"candidate_{index:02d}_{digest[:5]}", "rank": 0,
        "start": round(start, 2), "end": round(end, 2), "duration": round(max(0, end - start), 2),
        "transcript_excerpt": text, "text": text, "profile": profile_name,
        "title_options": raw.get("title_options") or [raw.get("title") or "Momen pilihan", "Inti pembahasan", "Bagian penting"],
        "title": raw.get("title") or "Momen pilihan", "reason": raw.get("reason", "Skor lokal dan cakupan sumber"),
        "confidence": round(float(raw.get("confidence", .6)), 3), "viral_readiness": score,
        "readiness": score, "score": score, "score_breakdown": breakdown, "breakdown": breakdown,
        "warnings": warnings, "overlap_percentage": 0, "topic_cluster": topic_cluster(text),
        "speaker": raw.get("speaker"), "scene": raw.get("scene"), "selected": bool(raw.get("selected", False)),
        "pinned": bool(raw.get("pinned", False)), "banned": bool(raw.get("banned", False)),
        "status": raw.get("status", "draft_candidate"), "estimated_output": f"MP4 {round(max(0, end-start))} dtk + SRT + metadata JSON",
        "series_potential": min(100, round(breakdown["novelty"] * .45 + breakdown["information_density"] * .55)),
    }


def rerank(items: list[dict], profile_name: str, diversity: float = 0.3, max_overlap: float = 0.35) -> list[dict]:
    pool = [normalize(x, i + 1, profile_name, max([float(y.get("end", y.get("e", 0))) for y in items] + [1])) for i, x in enumerate(items)]
    selected: list[dict] = []
    while pool:
        def utility(candidate: dict) -> tuple:
            redundancy = max((similarity(candidate, value) for value in selected), default=0)
            scene_bonus = 4 if candidate.get("scene") and all(candidate.get("scene") != x.get("scene") for x in selected) else 0
            speaker_bonus = 3 if candidate.get("speaker") and all(candidate.get("speaker") != x.get("speaker") for x in selected) else 0
            value = candidate["score"] * (1 - diversity) - redundancy * 100 * diversity + scene_bonus + speaker_bonus
            if candidate["pinned"]:
                value += 1000
            if candidate["banned"]:
                value -= 2000
            return (round(value, 8), candidate["score"], -candidate["start"], candidate["id"])
        chosen = max(pool, key=utility)
        pool.remove(chosen)
        if chosen["banned"]:
            continue
        chosen["overlap_percentage"] = round(max((overlap(chosen, x) for x in selected), default=0) * 100, 1)
        keep = chosen["pinned"] or chosen.get("manual") or chosen.get("status") in {"queued", "rendering", "done"}
        if not keep and chosen["overlap_percentage"] > max_overlap * 100:
            continue
        selected.append(chosen)
    for rank, item in enumerate(selected, 1):
        item["rank"] = rank
    return selected


def rankings(items: list[dict]) -> dict:
    result = {}
    for goal, key in GOALS.items():
        result[goal] = [x["id"] for x in sorted(items, key=lambda x: (-float(x.get(key, x.get("score_breakdown", {}).get(key, 0))), x["rank"], x["id"]))]
    return result


def snap_boundary(start: float, end: float, segments: list[dict], tolerance: float = 2.5) -> tuple[float, float]:
    starts = [float(x["s"]) for x in segments]
    ends = [float(x["e"]) for x in segments]
    snap = lambda value, choices: min(choices, key=lambda x: (abs(x - value), x)) if choices and min(abs(x-value) for x in choices) <= tolerance else value
    fixed_start, fixed_end = snap(start, starts), snap(end, ends)
    return (round(max(0, fixed_start), 2), round(max(fixed_start + 1, fixed_end), 2))


def chunk_ranges(duration: float, size: float = 900, overlap_seconds: float = 30) -> list[tuple[float, float]]:
    if duration <= size:
        return [(0.0, round(duration, 2))]
    step = max(1.0, size - overlap_seconds)
    out, start = [], 0.0
    while start < duration:
        out.append((round(start, 2), round(min(duration, start + size), 2)))
        if start + size >= duration:
            break
        start += step
    return out


def manifest(items: list[dict], profile_name: str, source: str, revision: int = 1) -> dict:
    return {"schema_version": SCHEMA_VERSION, "revision": revision, "source": source, "profile": profile_name,
            "candidate_count": len(items), "candidates": items, "rankings": rankings(items),
            "score_note": "Viral Readiness adalah alat review, bukan ramalan viral.",
            "rights_checklist": {"source_permission": False, "attribution": False, "music": False,
                                 "face_voice": False, "product_claims": False, "sponsor_disclosure": False,
                                 "note": "Checklist editorial, bukan nasihat hukum dan tidak memblokir workflow."}}
