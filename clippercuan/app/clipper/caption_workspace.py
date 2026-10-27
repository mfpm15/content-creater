"""Transcript quality, glossary, cue editing, caption templates, and validation.

Scores are diagnostics, never WER: no ground-truth transcript is available.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import time
from pathlib import Path

SCHEMA_VERSION = 3
TOKEN_RE = re.compile(r"[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)*", re.UNICODE)
UNKNOWN_RE = re.compile(r"(?:<unk>|\[inaudible\]|\?\?+)", re.I)
PROTECTED_RE = re.compile(
    r"(?:\b(?:Rp|IDR|USD|GB|TB|MB|GHz|MHz|Hz|W|mAh|MP|fps|kg|km|cm|mm|ms)\s?\d[\w.,-]*|"
    r"\b\d+(?:[.,]\d+)?\s?(?:GB|TB|MB|GHz|MHz|Hz|W|mAh|MP|fps|kg|km|cm|mm|ms|%|rupiah|dolar)\b)",
    re.I,
)

GLOSSARY_PROFILES = {
    "podcast": ["podcast", "host", "narasumber", "episode", "hot take"],
    "tech_review": ["Android", "iOS", "RAM", "SSD", "OLED", "AMOLED", "USB-C", "Wi-Fi", "Bluetooth", "benchmark", "chipset", "mAh", "GHz"],
    "mobile_legends": ["Mobile Legends", "MLBB", "EXP Lane", "Gold Lane", "Jungler", "Roamer", "Lord", "Turtle", "Retribution", "Flicker", "Savage", "Maniac", "Immortal"],
}

TEMPLATES = {
    "clean-pro": {"label": "Clean Pro", "profiles": ["podcast", "tech_review"], "font": "Anton", "size": 68, "weight": 700, "line_height": 1.14, "color": "#FFFFFF", "stroke": 5, "shadow": 2, "background": "#00000099", "highlight": "#FFD166", "position": "bottom", "animation": "none", "safe_area": .15, "max_words": 7, "max_chars": 34, "style": "clean", "uppercase": False},
    "bold-viral": {"label": "Bold Viral", "profiles": ["podcast", "mobile_legends"], "font": "Anton", "size": 82, "weight": 800, "line_height": 1.05, "color": "#FFFFFF", "stroke": 7, "shadow": 3, "background": "#000000B0", "highlight": "#FFC933", "position": "middle", "animation": "subtle-pop", "safe_area": .16, "max_words": 5, "max_chars": 26, "style": "box", "uppercase": True},
    "karaoke-focus": {"label": "Karaoke Focus", "profiles": ["podcast", "tech_review", "mobile_legends"], "font": "Anton", "size": 74, "weight": 800, "line_height": 1.08, "color": "#FFFFFF", "stroke": 6, "shadow": 2, "background": "#00000099", "highlight": "#54E6A5", "position": "bottom", "animation": "word-focus", "safe_area": .16, "max_words": 6, "max_chars": 30, "style": "karaoke", "uppercase": False},
    "podcast-quote": {"label": "Podcast Quote", "profiles": ["podcast"], "font": "Anton", "size": 72, "weight": 700, "line_height": 1.12, "color": "#FFFFFF", "stroke": 5, "shadow": 3, "background": "#171A2FCC", "highlight": "#B8A1FF", "position": "middle", "animation": "smooth-rise", "safe_area": .18, "max_words": 8, "max_chars": 36, "style": "clean", "uppercase": False},
    "tech-review": {"label": "Tech Review", "profiles": ["tech_review"], "font": "Anton", "size": 68, "weight": 700, "line_height": 1.1, "color": "#F8FAFC", "stroke": 5, "shadow": 2, "background": "#07111CCC", "highlight": "#38BDF8", "position": "bottom", "animation": "word-focus", "safe_area": .16, "max_words": 7, "max_chars": 34, "style": "karaoke", "uppercase": False},
    "gaming-energy": {"label": "Gaming Energy", "profiles": ["mobile_legends"], "font": "Bangers", "size": 80, "weight": 800, "line_height": 1.04, "color": "#FFFFFF", "stroke": 7, "shadow": 3, "background": "#120923B8", "highlight": "#FF5D8F", "position": "top", "animation": "subtle-pop", "safe_area": .18, "max_words": 5, "max_chars": 27, "style": "box", "uppercase": True},
    "minimal-lower-third": {"label": "Minimal Lower Third", "profiles": ["podcast", "tech_review", "mobile_legends"], "font": "Anton", "size": 58, "weight": 600, "line_height": 1.16, "color": "#FFFFFF", "stroke": 4, "shadow": 2, "background": "#000000B8", "highlight": "#FFFFFF", "position": "bottom", "animation": "none", "safe_area": .2, "max_words": 8, "max_chars": 38, "style": "clean", "uppercase": False},
}


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def timing_mode(words: list[dict]) -> str:
    if not words:
        return "none"
    synthetic = sum(bool(w.get("synthetic_timing")) for w in words)
    return "phrase-estimated" if synthetic > len(words) / 2 else "word"


def quality_report(transcript: dict, duration: float | None = None) -> dict:
    words = transcript.get("words") or []
    source = transcript.get("source") or "unknown"
    duration = float(duration or transcript.get("duration") or (words[-1].get("e", 0) if words else 0) or 0)
    mode = timing_mode(words)
    base = {"youtube-manual": 90, "youtube-auto": 76, "whisper-lokal": 80, "api": 78}.get(source, 55)
    spoken = sum(max(0, float(w.get("e", 0)) - float(w.get("s", 0))) for w in words)
    coverage = min(1.0, spoken / duration) if duration else (1.0 if words else 0.0)
    probs = [float(w["p"]) for w in words if isinstance(w.get("p"), (int, float))]
    confidence = sum(probs) / len(probs) if probs else None
    gaps = [max(0, float(b.get("s", 0)) - float(a.get("e", 0))) for a, b in zip(words, words[1:])]
    suspicious = sum(g > 2.5 for g in gaps)
    span = max(.001, (float(words[-1]["e"]) - float(words[0]["s"]))) if words else 1
    wps = len(words) / span
    unknown = sum(bool(UNKNOWN_RE.search(str(w.get("w", "")))) for w in words)
    repetitions = sum(str(a.get("w", "")).casefold() == str(b.get("w", "")).casefold() for a, b in zip(words, words[1:]))
    scripts = set()
    joined = " ".join(str(w.get("w", "")) for w in words)
    if re.search(r"[A-Za-zÀ-ÿ]", joined): scripts.add("latin")
    if re.search(r"[\u4e00-\u9fff]", joined): scripts.add("han")
    if re.search(r"[\u0600-\u06ff]", joined): scripts.add("arabic")
    mixed = len(scripts) > 1
    score = float(base)
    score += (coverage - .65) * 22
    if confidence is not None: score += (confidence - .75) * 24
    if mode != "word": score -= 8
    score -= min(14, suspicious * 2.5) + min(8, unknown * 2) + min(8, repetitions)
    if not (.8 <= wps <= 4.5): score -= 8
    warnings = []
    if coverage < .35: warnings.append("Coverage ujaran rendah; sumber mungkin tidak lengkap atau audio buruk.")
    if suspicious: warnings.append(f"{suspicious} jeda lebih dari 2,5 detik perlu diperiksa.")
    if mixed: warnings.append("Beberapa sistem tulisan terdeteksi; periksa bahasa campuran dan istilah teknis.")
    if unknown: warnings.append(f"{unknown} token tidak dikenal perlu koreksi manual.")
    if wps > 4.5: warnings.append("Laju kata sangat cepat; cue perlu diperlambat atau dipecah.")
    if mode != "word": warnings.append("Timing per kata diperkirakan; active-word presisi dinonaktifkan.")
    if source == "youtube-auto": warnings.append("Subtitle YouTube otomatis; realign atau transkripsi lokal tersedia untuk istilah khusus.")
    return {"schema_version": SCHEMA_VERSION, "kind": "diagnostic_not_wer", "score": round(max(0, min(100, score))), "source": source, "coverage": round(coverage, 3), "timing_mode": mode, "confidence": None if confidence is None else round(confidence, 3), "suspicious_gaps": suspicious, "words_per_second": round(wps, 2), "repetitions": repetitions, "unknown_tokens": unknown, "language": transcript.get("language"), "mixed_language_warning": mixed, "warnings": warnings}


def glossary(profile: str, custom: list[dict] | None = None) -> list[dict]:
    return [{"canonical": item, "variants": [], "profile": profile} for item in GLOSSARY_PROFILES.get(profile, [])] + list(custom or [])


def apply_glossary(words: list[dict], entries: list[dict]) -> tuple[list[dict], list[dict]]:
    out = copy.deepcopy(words)
    audit = []
    for index, word in enumerate(out):
        raw = str(word.get("w", ""))
        bare = raw.strip(".,!?;:")
        suffix = raw[len(bare):] if raw.startswith(bare) else ""
        for entry in entries:
            canonical = str(entry.get("canonical", "")).strip()
            variants = [str(v).casefold() for v in entry.get("variants", []) if str(v).strip()]
            if canonical and bare.casefold() in variants:
                before = word["w"]
                word["w"] = canonical + suffix
                audit.append({"op": "glossary", "index": index, "before": before, "after": word["w"], "at": time.time()})
                break
    return out, audit


def _protected_tokens(text: str) -> set[str]:
    protected = {match.group(0).casefold() for match in PROTECTED_RE.finditer(text)}
    for values in GLOSSARY_PROFILES.values():
        protected.update(value.casefold() for value in values if " " in value or any(ch.isdigit() for ch in value))
    return protected


def segment(words: list[dict], max_words: int = 7, max_chars: int = 34, pause: float = .55) -> list[list[dict]]:
    chunks, current = [], []
    protected = _protected_tokens(" ".join(str(w.get("w", "")) for w in words))
    for index, word in enumerate(words):
        current.append(word)
        text = " ".join(str(item.get("w", "")) for item in current)
        next_gap = float(words[index + 1].get("s", 0)) - float(word.get("e", 0)) if index + 1 < len(words) else 99
        punctuation = str(word.get("w", "")).endswith((".", "?", "!", "…", ":", ";"))
        limit = len(current) >= max_words or len(text) >= max_chars
        protected_tail = any(text.casefold().endswith(entity) for entity in protected)
        if punctuation or next_gap > pause or (limit and not protected_tail):
            chunks.append(current); current = []
    if current: chunks.append(current)
    if len(chunks) > 1 and len(chunks[-1]) == 1 and len(chunks[-2]) < max_words:
        chunks[-2].extend(chunks.pop())
    return chunks


def normalize_cues(items: list[dict]) -> list[dict]:
    """Deduplicate identical spoken cues and trim overlaps without deleting text."""
    out = []
    for raw in sorted(copy.deepcopy(items), key=lambda cue: (float(cue.get("start", 0)), float(cue.get("end", 0)))):
        cue = {**raw, "role": raw.get("role") or "spoken-caption",
               "provenance": raw.get("provenance") or "transcript"}
        key = " ".join(str(cue.get("text", "")).casefold().split())
        duplicate = next((old for old in out if old["role"] == cue["role"]
                          and " ".join(str(old.get("text", "")).casefold().split()) == key
                          and float(cue["start"]) < float(old["end"])), None)
        if duplicate:
            duplicate["start"] = min(float(duplicate["start"]), float(cue["start"]))
            duplicate["end"] = max(float(duplicate["end"]), float(cue["end"]))
            duplicate["provenance"] = f"{duplicate['provenance']}+{cue['provenance']}"
            continue
        out.append(cue)
    for left, right in zip(out, out[1:]):
        if left["role"] == right["role"] == "spoken-caption" and float(left["end"]) > float(right["start"]):
            left["end"] = max(float(left["start"]), float(right["start"]))
    return out


def cues(words: list[dict], config: dict | None = None) -> list[dict]:
    config = config or {}
    groups = segment(words, int(config.get("max_words", 7)), int(config.get("max_chars", 34)))
    result = [{"id": f"cue-{index + 1}", "start": float(group[0]["s"]), "end": float(group[-1]["e"]) + .12,
               "text": " ".join(w["w"] for w in group), "words": copy.deepcopy(group),
               "role": "spoken-caption", "provenance": group[0].get("provenance", "transcript")}
              for index, group in enumerate(groups)]
    return normalize_cues(result)


def validate_cues(items: list[dict], frame: tuple[int, int] = (1080, 1920), safe_area: float = .15) -> dict:
    warnings = []
    previous = 0.0
    for index, cue in enumerate(items):
        start, end, text = float(cue.get("start", 0)), float(cue.get("end", 0)), str(cue.get("text", "")).strip()
        duration = end - start
        chars = len(text.replace("\n", ""))
        cps = chars / duration if duration > 0 else math.inf
        words = len(text.split())
        wps = words / duration if duration > 0 else math.inf
        if start < previous - .001: warnings.append({"cue": index, "code": "overlap", "message": "Cue bertumpuk."})
        if duration < .5: warnings.append({"cue": index, "code": "too-short", "message": "Durasi cue kurang dari 0,5 detik."})
        if duration > 7: warnings.append({"cue": index, "code": "too-long", "message": "Durasi cue lebih dari 7 detik."})
        if cps > 20: warnings.append({"cue": index, "code": "cps", "message": f"{cps:.1f} CPS melebihi batas kerja 20."})
        if wps > 4.5: warnings.append({"cue": index, "code": "wps", "message": f"{wps:.1f} kata/detik terlalu cepat."})
        if text.count("\n") > 1: warnings.append({"cue": index, "code": "lines", "message": "Lebih dari dua baris."})
        if len(text.split()) == 1: warnings.append({"cue": index, "code": "orphan", "message": "Kata tunggal terisolasi."})
        previous = max(previous, end)
    width, height = frame
    return {"valid": not any(w["code"] in {"overlap", "too-short", "lines"} for w in warnings), "warnings": warnings, "safe_zone": {"x": round(width * safe_area), "y": round(height * safe_area), "width": round(width * (1 - 2 * safe_area)), "height": round(height * (1 - 2 * safe_area))}}


def recommend(profile: str, quality: dict) -> str:
    if quality.get("timing_mode") != "word": return "clean-pro"
    return {"podcast": "podcast-quote", "tech_review": "tech-review", "mobile_legends": "gaming-energy"}.get(profile, "clean-pro")


def workspace(transcript: dict, duration: float, profile: str = "podcast", custom_glossary: list[dict] | None = None) -> dict:
    report = quality_report(transcript, duration)
    return {"schema_version": SCHEMA_VERSION, "revision": 1, "transcript": transcript, "quality_report": report,
            "glossary": glossary(profile, custom_glossary), "cues": cues(transcript.get("words") or []),
            "layers": [{"role": "video", "active": True}, {"role": "hook", "active": False},
                       {"role": "spoken-caption", "active": True}, {"role": "emoji", "active": False}],
            "caption_layers": 1, "source_has_burned_captions": "unknown", "templates": TEMPLATES,
            "recommended_template": recommend(profile, report), "audit_trail": [], "undo_stack": [],
            "redo_stack": [], "updated_at": time.time()}
