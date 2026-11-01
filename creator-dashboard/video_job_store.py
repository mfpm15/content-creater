"""Atomic local job checkpoints, without provider configuration or credentials."""
import json
import os
from pathlib import Path
from security import redact


def save_job(directory: Path, job: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    key = job["jobId"]
    if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
        return  # historical or test-only in-memory job
    path = directory / (key + ".json")
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(redact(json.dumps(job, ensure_ascii=False)))
        out.flush()
        os.fsync(out.fileno())
    temp.replace(path)


def recover_jobs(directory: Path) -> dict:
    result = {}
    for path in directory.glob("*.json"):
        try:
            job = json.loads(path.read_text("utf-8"))
            if job["jobId"] != path.stem:
                continue
            if job.get("status") not in {"awaiting_scene_plan", "awaiting_storyboard", "succeeded", "failed"}:
                job.update(status="interrupted", error="Pekerjaan terputus; periksa checkpoint sebelum melanjutkan")
            result[job["jobId"]] = job
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result
