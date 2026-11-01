"""Private, atomic checkpoints; restored work always needs explicit continuation."""
import json
import os
import stat
import tempfile
from pathlib import Path

from security import redact_tree as _redact_tree

MAX_CHECKPOINT_BYTES = 4_000_000


def _job_key(value: object) -> bool:
    return isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value)


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path,'is_junction',lambda:False)())


def save_job(directory: Path, job: dict) -> None:
    key = job['jobId']
    if not _job_key(key):
        return  # historical/test-only in-memory job
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if _linked(directory):
        raise ValueError('Checkpoint directory must not be a symbolic link')
    data = json.dumps(_redact_tree(job), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(data) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Checkpoint melebihi batas ukuran')
    fd, name = tempfile.mkstemp(prefix=key + '-', suffix='.tmp', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(directory / (key + '.json'))
    finally:
        temporary.unlink(missing_ok=True)


def recover_jobs(directory: Path) -> dict:
    result = {}
    if _linked(directory):
        return result
    for path in directory.glob('*.json'):
        if not _job_key(path.stem) or _linked(path):
            continue
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb') as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CHECKPOINT_BYTES:
                    continue
                job = json.loads(source.read(MAX_CHECKPOINT_BYTES + 1))
            if not isinstance(job, dict) or job.get('jobId') != path.stem:
                continue
            revision = job.get('revision', 0)
            if type(revision) is not int or revision < 0 or not isinstance(job.get('status'), str):
                continue
            job['revision'] = revision
            if job.get('scenePlan') is not None and not isinstance(job['scenePlan'], dict):
                continue
            if job['status'] not in {'awaiting_scene_plan', 'awaiting_storyboard', 'succeeded', 'failed'}:
                job.update(status='interrupted', error='Pekerjaan terputus; periksa checkpoint sebelum melanjutkan')
            result[job['jobId']] = _redact_tree(job)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result
