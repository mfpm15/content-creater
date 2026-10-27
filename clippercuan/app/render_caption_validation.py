"""Render reproducible caption validation outputs and extract inspection frames."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from clipper import media, render
from clipper.config import DEFAULTS, FFMPEG, deep_merge
from clipper.recipes import RECIPES

PROJECT = Path(os.environ.get(
    "CLIPPER_VALIDATION_PROJECT",
    Path.home() / "ClipperCuan" / "projects" / "20261027-073927-9a67",
))
TIMES = (0.35, 1.25, 2.50, 4.00, 5.75, 7.50, 9.25, 11.00, 12.75, 14.50, 16.50, 19.00)


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text("utf-8"))


def choose_clip() -> dict:
    manifest = load_json(PROJECT / "candidate-manifest.json")
    clips = manifest.get("candidates", manifest if isinstance(manifest, list) else [])
    return next((item for item in clips if item.get("id") == "candidate_01"), clips[0])


def load_words(clip: dict) -> list[dict]:
    """Prefer candidate-local words when validating an already rendered remote-project artifact."""
    if clip.get("words"):
        return clip["words"]
    payload = load_json(PROJECT / "transcript.json")
    return payload.get("words", payload if isinstance(payload, list) else [])


def validation_configs() -> dict[str, dict]:
    """Resolve Box Punch V2 variants from the production recipe with runtime-neutral overrides."""
    common = {
        "layout": "portrait", "smart_crop": False, "cut_silence": False,
        "caption_layers": 1, "source_has_burned_captions": "no",
        "quality": {"output": "1080", "encoder": "cpu", "sharpen": True},
        "title": {"enabled": False},
        "progress_bar": {"enabled": False}, "cta": {"enabled": False},
        "watermark": {"enabled": False},
        "composition": {"subtle_punch_in": False, "scene_aware": False},
    }
    out = {"raw_measurement_reference": deep_merge(DEFAULTS, deep_merge(common, {
        "caption": {"enabled": False, "template_id": "none/raw", "preset": "none/raw"},
        "decoration": {"mode": "none", "provenance": None, "max_active": 1},
        "emoji": {"enabled": False},
    }))}
    variants = {
        "box_punch_v2_clean": {"decoration": {"mode": "none", "provenance": None, "max_active": 1},
                               "emoji": {"enabled": False, "provenance": "keyword"}},
        "box_punch_v2_smart_emoji": {"decoration": {"mode": "smart_emoji", "provenance": "keyword", "max_active": 1},
                                     "emoji": {"enabled": True, "size": 1.0, "provenance": "keyword"}},
        "box_punch_v2_light_illustration": {"decoration": {"mode": "light_illustration", "provenance": "manual", "max_active": 1},
                                            "emoji": {"enabled": False, "provenance": "manual"}},
    }
    for label, variant in variants.items():
        cfg = deep_merge(DEFAULTS, RECIPES["box-punch"]["settings"])
        cfg = deep_merge(cfg, common)
        cfg = deep_merge(cfg, variant)
        cfg["recipe"] = "box-punch"
        cfg["recipe_applied"] = "box-punch"
        out[label] = cfg
    return out


def extract_frames(video: Path, frame_dir: Path, duration: float) -> list[dict]:
    frame_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, requested in enumerate(TIMES, 1):
        timestamp = min(requested, max(0.05, duration - 0.05))
        full = frame_dir / f"frame_{index:02d}_{timestamp:05.2f}_full.png"
        crop = frame_dir / f"frame_{index:02d}_{timestamp:05.2f}_caption.png"
        subprocess.run([
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
            "-i", str(video), "-frames:v", "1", str(full),
        ], check=True)
        subprocess.run([
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
            "-i", str(video), "-frames:v", "1", "-vf", "crop=1080:620:0:1200", str(crop),
        ], check=True)
        records.append({"index": index, "timestamp": timestamp, "full": full.name, "crop": crop.name})
    return records


def main() -> int:
    if not PROJECT.is_dir():
        raise FileNotFoundError(f"Project tidak ditemukan: {PROJECT}")
    original = choose_clip()
    source = PROJECT / "source.mkv"
    using_candidate_source = not source.is_file()
    if using_candidate_source:
        source = PROJECT / (original.get("file") or "candidate_01.mp4")
    if not source.is_file():
        raise FileNotFoundError(f"Source tidak ditemukan: {source}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit = PROJECT / f"box_punch_v2_validation_{stamp}"
    audit.mkdir(parents=True, exist_ok=False)
    probe = media.probe(source)
    words = load_words(original)
    if using_candidate_source:
        source_probe = media.probe(source)
        duration = float(source_probe.duration or max((w.get("e", 0) for w in words), default=0))
        original = {**original, "start": 0.0, "end": duration, "words": words}
    results = {}

    for label, cfg in validation_configs().items():
        work = audit / label
        work.mkdir()
        clip_id = f"validation_{label}"
        clip = {
            **original,
            "id": clip_id,
            "title": "",
            "crop_keys": [],
            "words": None,
        }
        result = render.render_clip(work, source, probe, clip, cfg, words)
        video = work / result["file"]
        frames = extract_frames(video, work / "frames", float(result["duration"]))
        root_video = audit / f"validation_{label}_{stamp}.mp4"
        shutil.copy2(video, root_video)
        results[label] = {
            **result,
            "video": root_video.name,
            "work": label,
            "frames": frames,
            "root_sidecar_count": len(list(audit.glob(f"{clip_id}.*rt"))) + len(list(audit.glob(f"{clip_id}.ass"))),
        }

    report = {
        "schema_version": 2,
        "render_path": "clipper.render.render_clip (same production entrypoint used by API/UI)",
        "configuration_source": "clipper.recipes.RECIPES['box-punch']; orchestration overrides are runtime-neutral",
        "caption_style_overrides": False,
        "measurement_reference": "raw_measurement_reference is not an A/B candidate",
        "validation_scope": "Box Punch V2 clean, smart emoji, and light illustration modes",
        "project": str(PROJECT), "audit": str(audit), "source": str(source),
        "source_kind": "candidate-local-render" if using_candidate_source else "original-source",
        "clip": {"id": original.get("id"), "start": original["start"], "end": original["end"]},
        "frame_count_per_output": len(TIMES), "results": results,
    }
    (audit / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(f"AUDIT_DIR={audit}")
    for label, result in results.items():
        print(f"{label.upper()}_VIDEO={audit / result['video']}")
        print(f"{label.upper()}_FRAMES={len(result['frames'])}")
        print(f"{label.upper()}_SIDECAR_AUTOLOAD_SAFE={result.get('sidecar_autoload_safe')}")
        print(f"{label.upper()}_ROOT_SIDECARS={result['root_sidecar_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
