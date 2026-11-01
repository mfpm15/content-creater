"""Measured silence snapping with word-coverage and duration invariants."""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

from . import media
from .caption_workspace import atomic_json
from .config import FFMPEG


def detect(audio: Path, duration: float, cache: Path | None = None) -> list[list[float]]:
    key = media.file_digest(audio)
    if cache and cache.exists():
        try:
            saved = json.loads(cache.read_text('utf-8'))
            if saved.get('key') == key: return saved['intervals']
        except (OSError, ValueError, KeyError): pass
    result = subprocess.run([FFMPEG, '-hide_banner', '-nostdin', '-protocol_whitelist', 'file,pipe', '-i', str(audio),
                             '-vn', '-af', 'silencedetect=noise=-35dB:d=0.25', '-f', 'null', '-'],
                            capture_output=True, timeout=max(60, min(600, duration)), creationflags=media._NO_WINDOW)
    if result.returncode: raise media.FFmpegError('Deteksi jeda audio gagal')
    intervals, start = [], None
    for kind, value in re.findall(r'silence_(start|end):\s*([\d.]+)', result.stderr.decode('utf-8', 'replace')):
        if kind == 'start': start = max(0, float(value))
        elif start is not None:
            intervals.append([start, min(duration, float(value))]); start = None
    if start is not None and start < duration: intervals.append([start, duration])
    if cache: atomic_json(cache, {'key': key, 'intervals': intervals, 'method': 'ffmpeg_silencedetect_-35dB_250ms'})
    return intervals


def snap(start: float, end: float, words: list[dict], pauses: list[list[float]], duration: float,
         minimum: float, maximum: float, tolerance: float = .75) -> dict:
    if not all(math.isfinite(v) for v in (start, end, duration, minimum, maximum)):
        raise ValueError('Waktu tidak valid')
    covered = [i for i, w in enumerate(words) if float(w['e']) > start and float(w['s']) < end]
    if not covered: return {'start': start, 'end': end, 'changed': False}
    mids = [(a + b) / 2 for a, b in pauses if 0 <= a < b <= duration]
    first, last = words[covered[0]], words[covered[-1]]
    starts = sorted({start, float(first['s']), *[t for t in mids if abs(t - start) <= tolerance]}, key=lambda t: (abs(t-start), t))
    ends = sorted({end, float(last['e']), *[t for t in mids if abs(t - end) <= tolerance]}, key=lambda t: (abs(t-end), t))
    # Prefer measured pauses over unchanged edges, while preserving every spoken word.
    starts.sort(key=lambda t: (t not in mids, abs(t-start)))
    ends.sort(key=lambda t: (t not in mids, abs(t-end)))
    for a in starts:
        for b in ends:
            if not (0 <= a <= float(first['s']) and float(last['e']) <= b <= duration and minimum <= b-a <= maximum): continue
            included = [i for i, w in enumerate(words) if float(w['e']) > a and float(w['s']) < b]
            if included == covered:
                return {'start': round(a, 3), 'end': round(b, 3), 'changed': (a,b) != (start,end),
                        'method': 'measured_pause_word_coverage_preserved'}
    return {'start': start, 'end': end, 'changed': False}
