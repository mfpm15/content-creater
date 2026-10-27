"""Single backend source of truth for content-profile pipeline decisions."""
from __future__ import annotations

import copy

_BASE_WEIGHTS = {
    "hook": 1.0, "standalone_clarity": 1.2, "payoff": 1.1, "novelty": 1.0,
    "emotion_humor": .8, "quotability": .9, "information_density": 1.0,
    "visual_activity": .7, "clean_ending": 1.1, "profile_fit": 1.2,
    "transcript_confidence": 1.0, "crop_confidence": .8, "rights_context_risk": -1.0,
}


def _profile(label: str, result: str, duration: tuple[float, float], recipe: str,
             crop_strategy: str, caption_policy: str, safe_zones: list[str],
             speaker_policy: str, terms: tuple[str, ...], **overrides) -> dict:
    weights = {**_BASE_WEIGHTS, **overrides.pop("weights", {})}
    return {
        "label": label, "result": result, "duration": duration, "recipe": recipe,
        "layout": overrides.pop("layout", "portrait"), "caption": caption_policy,
        "caption_policy": caption_policy, "crop": crop_strategy,
        "crop_strategy": crop_strategy, "safe_area": overrides.pop("safe_area", .15),
        "safe_zones": safe_zones, "speaker_policy": speaker_policy,
        "hook_policy": overrides.pop("hook_policy", "standalone-payoff"),
        "decoration_policy": overrides.pop("decoration_policy", "none"),
        "pacing": overrides.pop("pacing", "natural"), "weights": weights,
        "terms": terms, "status": overrides.pop("status", "Production"), **overrides,
    }


REGISTRY = {
    "general": _profile(
        "General", "Momen mandiri yang jelas untuk berbagai jenis konten", (20, 50),
        "recommended", "face-aware center crop dengan fallback tengah", "clean-large",
        ["spoken-caption", "face"], "single-speaker bila diarization tidak tersedia", (),
    ),
    "podcast": _profile(
        "Podcast", "Hot take, cerita mini, tanya-jawab, dan insight mandiri", (25, 60),
        "box-punch-podcast", "speaker-aware face crop", "box-punch-v2",
        ["spoken-caption", "face"], "diarization dan speaker label bila tersedia",
        ("podcast", "host", "narasumber", "cerita", "kenapa"),
        decoration_policy="emoji-hemat", weights={"quotability": 1.25, "clean_ending": 1.3, "visual_activity": .45},
    ),
    "interview": _profile(
        "Interview", "Pertanyaan dan jawaban utuh dengan konteks pembicara", (25, 60),
        "box-punch-podcast", "active-speaker face crop", "box-punch-v2",
        ["spoken-caption", "face"], "diarization wajib dipakai bila tersedia",
        ("wawancara", "interview", "narasumber", "pertanyaan", "jawab"),
        decoration_policy="emoji-minimal", weights={"standalone_clarity": 1.4, "clean_ending": 1.35},
    ),
    "review": _profile(
        "Review", "Masalah, perbandingan, verdict, dan value dengan konteks", (20, 50),
        "box-punch-review", "product-first crop; face fallback", "box-punch-v2",
        ["spoken-caption", "product"], "speaker label hanya saat lebih dari satu pembicara",
        ("review", "harga", "produk", "versus", "worth", "perbandingan"),
        decoration_policy="product-callout-separate", weights={"information_density": 1.35, "visual_activity": 1.05},
    ),
    "tech_review": _profile(
        "Tech Review", "Demo, spesifikasi, perbandingan, dan verdict produk teknologi", (20, 50),
        "box-punch-review", "product/demo-first crop; face fallback", "box-punch-v2",
        ["spoken-caption", "product", "demo"], "speaker label hemat",
        ("fitur", "spesifikasi", "kamera", "baterai", "performa", "teknologi"),
        decoration_policy="product-callout-separate", weights={"information_density": 1.45, "visual_activity": 1.1},
    ),
    "gaming": _profile(
        "Gaming", "Clutch, outplay, comeback, tip, reaksi, atau funny fail", (15, 40),
        "ml-hype", "gameplay crop dengan facecam-aware split", "gaming-hud-safe",
        ["spoken-caption", "minimap", "score", "controls", "kill-feed"], "facecam label bila tersedia",
        ("gaming", "gameplay", "clutch", "outplay", "comeback"), layout="split", pacing="fast",
        decoration_policy="hud-safe", weights={"visual_activity": 1.55, "emotion_humor": 1.25, "transcript_confidence": .5},
    ),
    "mobile_legends": _profile(
        "Mobile Legends", "Objective, team fight, outplay, rank tip, atau reaksi MLBB", (15, 40),
        "ml-hype", "gameplay crop dengan perlindungan HUD dan facecam", "gaming-hud-safe",
        ["spoken-caption", "minimap", "score", "controls", "kill-feed"], "facecam label bila tersedia",
        ("mobile legends", "mlbb", "lord", "turtle", "turret", "jungler", "savage"), layout="split", pacing="fast",
        decoration_policy="hud-safe", weights={"visual_activity": 1.6, "profile_fit": 1.45, "transcript_confidence": .45},
    ),
    "educational": _profile(
        "Educational", "Penjelasan bertahap, keyword penting, dan chapter ringkas", (25, 50),
        "clean-focus", "presenter-aware crop dengan ruang ilustrasi", "keyword-emphasis",
        ["spoken-caption", "face", "illustration"], "single presenter; chapter-aware",
        ("edukasi", "tutorial", "langkah", "cara", "pelajaran", "jelaskan"),
        hook_policy="learning-outcome", decoration_policy="light-illustration",
        weights={"information_density": 1.5, "standalone_clarity": 1.4, "visual_activity": .65},
    ),
}

ALIASES = {"auto": "general", "education": "educational", "mlbb": "mobile_legends"}


def canonical(name: str | None) -> str:
    value = ALIASES.get(name or "general", name or "general")
    return value if value in REGISTRY else "general"


def resolve(name: str | None) -> dict:
    profile_id = canonical(name)
    return {"id": profile_id, **copy.deepcopy(REGISTRY[profile_id])}


def resolve_selection(requested: str | None, classification: dict | None = None) -> dict:
    classification = classification or {}
    confidence = float(classification.get("confidence", 1 if requested not in (None, "auto") else 0))
    automatic = requested in (None, "", "auto")
    fallback = automatic and confidence < .5
    profile_id = "general" if fallback else canonical(classification.get("profile") if automatic else requested)
    resolved = resolve(profile_id)
    resolved.update({
        "requested": requested or "auto", "confidence": round(confidence, 3), "fallback": fallback,
        "evidence": list(classification.get("evidence") or classification.get("signals") or []),
        "reason": ("Confidence klasifikasi rendah; fallback General dan Clean Large"
                   if fallback else "Pilihan user" if not automatic else "Klasifikasi konten dan analisis media"),
    })
    return resolved


def public_registry() -> dict:
    return {profile_id: {k: copy.deepcopy(v) for k, v in data.items() if k not in {"terms"}}
            for profile_id, data in REGISTRY.items()}
