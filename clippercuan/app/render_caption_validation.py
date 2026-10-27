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


def load_words() -> list[dict]:
    payload = load_json(PROJECT / "transcript.json")
    return payload.get("words", payload if isinstance(payload, list) else [])


def validation_configs() -> dict[str, dict]:
    common = {
        "layout": "portrait",
        "smart_crop": False,
        "cut_silence": False,
        "caption_layers": 1,
        "source_has_burned_captions": "no",
        "quality": {"output": "1080", "encoder": "cpu", "sharpen": True},
        "title": {"enabled": False},
        "emoji": {"enabled": False},
        "progress_bar": {"enabled": False},
        "cta": {"enabled": False},
        "watermark": {"enabled": False},
        "composition": {"subtle_punch_in": False, "scene_aware": False},
    }
    return {
        "raw": deep_merge(DEFAULTS, deep_merge(common, {"caption": {"enabled": False}})),
        "baseline": deep_merge(DEFAULTS, deep_merge(common, {
            "caption": {
                "enabled": True, "role": "spoken-caption", "preset": "clean-pro",
                "style": "clean", "font": "Barlow Condensed", "size": 64,
                "outline": 3, "shadow": 0, "color": "#FFFFFF",
                "highlight": "#FFD166", "uppercase": False,
                "words_per_line": 4, "max_chars": 28, "safe_area": 0.18,
                "position": "bottom", "y_pct": 78, "animation": "none",
                "box": False, "effect": "none",
            }
        })),
        "enhanced_v2": deep_merge(DEFAULTS, deep_merge(common, {
            "caption": {
                "enabled": True, "role": "spoken-caption", "preset": "clean-focus",
                "style": "keyword", "font": "Barlow Condensed", "size": 66,
                "outline": 3, "shadow": 0, "color": "#FFFFFF",
                "highlight": "#FFD166", "uppercase": False,
                "words_per_line": 4, "max_chars": 28, "safe_area": 0.18,
                "position": "bottom", "y_pct": 76, "animation": "none",
                "box": False, "effect": "none", "accent_font": "Barlow Condensed",
                "accent_mode": "color", "accent_scale": 108,
            }
        })),
    }


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
    source = PROJECT / "source.mkv"
    if not source.is_file():
        raise FileNotFoundError(f"Source tidak ditemukan: {source}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit = PROJECT / f"caption_clean_validation_{stamp}"
    audit.mkdir(parents=True, exist_ok=False)
    probe = media.probe(source)
    original = choose_clip()
    words = load_words()
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
        root_video = audit / f"{clip_id}.mp4"
        shutil.copy2(video, root_video)
        results[label] = {
            **result,
            "video": root_video.name,
            "work": label,
            "frames": frames,
            "root_sidecar_count": len(list(audit.glob(f"{clip_id}.*rt"))) + len(list(audit.glob(f"{clip_id}.ass"))),
        }

    report = {
        "project": str(PROJECT),
        "audit": str(audit),
        "source": str(source),
        "clip": {"id": original.get("id"), "start": original["start"], "end": original["end"]},
        "frame_count_per_output": len(TIMES),
        "results": results,
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
