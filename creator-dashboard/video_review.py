"""Measured post-render review; no claim of visual/semantic correctness."""
import json
import shutil
import subprocess
from pathlib import Path


def review(path: Path, duration: float) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"status": "unmeasured", "issues": ["ffprobe unavailable"]}
    proc = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                          capture_output=True, check=False, timeout=60)
    if proc.returncode:
        return {"status": "failed", "issues": ["Artifact could not be probed"]}
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    actual = float(data.get("format", {}).get("duration", 0))
    issues = []
    if not any(s.get("codec_type") == "video" for s in streams): issues.append("Missing video")
    if not any(s.get("codec_type") == "audio" for s in streams): issues.append("Missing audio")
    if abs(actual - duration) > 0.5: issues.append("Duration differs from approved plan")
    return {"status": "needs_attention" if issues else "passed", "issues": issues,
            "duration": actual, "visual_review": "manual_required", "loudness": "unmeasured"}
