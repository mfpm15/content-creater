"""Reusable Opuscar scene-plan and composition CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(DASHBOARD))
import video_drafter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reusable dynamic Opuscar composition")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--script", default="")
    parser.add_argument("--script-file", type=Path)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--aspect", choices=video_drafter.ASPECT_RATIOS, default="9:16")
    parser.add_argument("--model", choices=video_drafter.ALLOWED_MODEL_IDS, default=video_drafter.LLM_MODEL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="Use deterministic proportional fallback without LLM")
    args = parser.parse_args()
    script = args.script_file.read_text(encoding="utf-8") if args.script_file else args.script
    explicit = video_drafter.parse_explicit_scenes(script)
    data = {}
    if not explicit and not args.offline:
        data = video_drafter._clean_json(video_drafter._call_9router(video_drafter.build_scene_prompt(args.topic, script, args.duration, args.aspect), args.model))
    plan = video_drafter.normalize_scene_plan(data, args.topic, script, args.duration)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "scene-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "audio-manifest.json").write_text(json.dumps(video_drafter.audio_manifest(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    video_drafter.write_subtitles(args.output / "subtitles.srt", plan)
    (args.output / "index.html").write_text(video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS[args.aspect], args.model), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sceneCount": len(plan["scenes"]), "duration": plan["duration"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
