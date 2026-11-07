"""Align Remotion highlight captions using actual Edge-TTS WordBoundary events.

The approved story plan is never mutated: only a render-specific copy receives
audio-derived cues. Missing, incomplete or invalid metadata is never replaced
with guessed word timings. Caption phrases still have estimated timings.
"""
from __future__ import annotations
import copy
import json
import re
from pathlib import Path

import creative_profile

TICKS = 10_000_000
MAX_WORDS = 400
MAX_METADATA_BYTES = 300_000
SCENE_ID = re.compile(r"scene-[1-9][0-9]{0,3}\Z")


def _read_cues(file: Path, scene: dict) -> list[dict]:
    if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= MAX_METADATA_BYTES:
        raise ValueError("Metadata WordBoundary hilang atau terlalu besar")
    start, end = float(scene["start"]), float(scene["end"])
    cues = []
    previous = start
    for line in file.read_text("utf-8").splitlines():
        if len(cues) >= MAX_WORDS:
            raise ValueError("Terlalu banyak kata dalam satu adegan")
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict) or item.get("type") != "WordBoundary":
            continue
        offset, duration, text = item.get("offset"), item.get("duration"), item.get("text")
        if type(offset) is not int or type(duration) is not int or offset < 0 or duration <= 0 or not isinstance(text, str) or not text.strip() or len(text) > 100:
            raise ValueError("Metadata kata dari provider tidak valid")
        s = round(start + offset / TICKS, 4)
        e = round(start + (offset + duration) / TICKS, 4)
        if s < previous - .025 or e > end + .05 or e <= s:
            raise ValueError("Timing kata melampaui slot suara adegan")
        s = max(previous, s)
        e = min(end, e)
        if e <= s:
            raise ValueError("Timing kata saling bertabrakan")
        cues.append({"word": text, "start": s, "end": e})
        previous = e
    if not cues:
        raise ValueError("Provider tidak mengirim WordBoundary")
    # This also ensures the complete spoken text, numbers and negation are
    # preserved. Incomplete or paraphrased TTS metadata is not labelled aligned.
    verified = copy.deepcopy(scene)
    creative_profile.timing(verified, {"wordCues": cues})
    return verified["wordCues"]


def enrich(plan: dict, target: Path) -> tuple[dict, dict]:
    render_plan = copy.deepcopy(plan)
    report = {"method": "edge_tts_word_boundaries", "alignedScenes": [], "warnings": [],
              "note": "Timestamp berasal dari event WordBoundary Edge-TTS untuk audio yang dirender, bukan estimasi atau transkripsi independen."}
    for scene in render_plan.get("scenes", []):
        sid = scene.get("id", "")
        if scene.get("wordCues"):
            report["warnings"].append({"scene": sid, "reason": "Cue kata pengguna dipertahankan"})
            continue
        if not isinstance(sid, str) or not SCENE_ID.fullmatch(sid):
            report["warnings"].append({"scene": str(sid)[:64], "reason": "ID adegan tidak didukung"})
            continue
        file = target / "voice" / (sid + ".words.jsonl")
        try:
            cues = _read_cues(file, scene)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError) as exc:
            report["warnings"].append({"scene": sid, "reason": "WordBoundary tidak lengkap/valid, caption memakai waktu frasa",
                                       "errorType": type(exc).__name__})
            continue
        scene["wordCues"] = cues
        scene["wordCueSource"] = "edge_tts"
        report["alignedScenes"].append({"scene": sid, "words": len(cues)})
    report["aligned"] = bool(report["alignedScenes"])
    return render_plan, report
