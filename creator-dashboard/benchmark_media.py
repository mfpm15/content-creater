"""Opt-in local benchmark. Download fixtures separately; no media or models are fetched."""
import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from article_storage import atomic_bytes, json_bytes
from security import redact, redact_tree
from video_review import _audio


def compare_cuts(actual: list[float], expected: list[float], tolerance: float) -> dict:
    """Ordered one-to-one matching, so duplicate detections cannot inflate recall."""
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Tolerance must be finite and positive')
    if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in actual+expected):
        raise ValueError('Cuts must be finite nonnegative timestamps')
    found, wanted = sorted(actual), sorted(expected)
    left = right = 0
    deltas = []
    while left < len(found) and right < len(wanted):
        delta = found[left]-wanted[right]
        if abs(delta) <= tolerance:
            deltas.append(round(delta, 6))
            left += 1
            right += 1
        elif delta < 0:
            left += 1
        else:
            right += 1
    precision = len(deltas)/len(found) if found else None
    recall = len(deltas)/len(wanted) if wanted else None
    return {'tolerance_seconds': tolerance, 'expected': wanted, 'detected': found, 'matched': len(deltas),
            'false_positives': len(found)-len(deltas), 'missed': len(wanted)-len(deltas),
            'precision': precision, 'recall': recall, 'matched_delta_seconds': deltas}


def measure(path: Path, expected_hash: str | None = None, sample: list[float] | None = None,
            expected_cuts: list[float] | None = None, tolerance: float = .12) -> dict:
    if not path.is_file():
        raise ValueError('Provide a local media file')
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if expected_hash and (not re.fullmatch('[a-fA-F0-9]{64}', expected_hash) or digest != expected_hash.lower()):
        raise ValueError('Fixture SHA256 mismatch')
    ffprobe, ffmpeg = shutil.which('ffprobe'), shutil.which('ffmpeg')
    if not ffprobe or not ffmpeg:
        raise ValueError('FFmpeg and ffprobe are required')
    probe = subprocess.run([ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_format',
                            '-show_streams', '-of', 'json', str(path.resolve())], capture_output=True, timeout=60, check=True)
    data = json.loads(probe.stdout)
    duration = float(data['format']['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid media duration')
    version = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True, timeout=10, check=True).stdout.splitlines()[0]
    report = {'schema': 1, 'measured_at_utc': datetime.now(timezone.utc).isoformat(),
              'fixture': {'name': path.name, 'sha256': digest, 'bytes': path.stat().st_size,
                                     'duration_seconds': duration},
              'runtime': {'os': platform.system(), 'python': platform.python_version(), 'ffmpeg': version},
              'asr_alignment': {'status': 'not_run', 'reason': 'No model invocation or download in this benchmark'},
              'limitations': ['One fixture is not a representative corpus', 'No face/cursor/speaker or semantic quality measurement']}
    before = time.perf_counter()
    audio = _audio(path.resolve(), ffmpeg) if any(s['codec_type'] == 'audio' for s in data['streams']) else {'status': 'not_present'}
    report['audio'] = {**audio, 'wall_seconds': round(time.perf_counter()-before, 3)}
    if sample:
        # Optional tooling only: the dashboard server does not import Clipper dependencies.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'clippercuan'/'app'))
        try:
            from clipper.reference_study import analyze
        except ImportError as exc:
            raise ValueError('Scene study requires the Clipper virtual environment') from exc
        # The sample uses the same bounded pipeline as the product, without a transcript.
        before = time.perf_counter()
        study = analyze(path.resolve(), [], duration, *sample)
        report['scene_study'] = {'wall_seconds': round(time.perf_counter()-before, 3), 'report': study}
        if expected_cuts is not None:
            span = study['sample']['end']-study['sample']['start']
            if any(cut >= span for cut in expected_cuts):
                raise ValueError('Expected cuts must fall inside the sampled time range')
            report['scene_study']['cut_comparison'] = compare_cuts(study['cuts_relative_seconds'], expected_cuts, tolerance)
    elif expected_cuts is not None:
        raise ValueError('Expected cuts require --scene-sample')
    return redact_tree(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--scene-sample', nargs=2, type=float, metavar=('START', 'SECONDS'))
    parser.add_argument('--expected-cuts', nargs='*', type=float)
    parser.add_argument('--tolerance', type=float, default=.12)
    args = parser.parse_args()
    try:
        report = measure(args.media, args.expected_sha256, args.scene_sample, args.expected_cuts, args.tolerance)
        atomic_bytes(args.output, json_bytes(report))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = redact(str(exc)) if isinstance(exc, ValueError) else type(exc).__name__
        parser.exit(1, f'Benchmark failed: {reason}\n')
    print(json.dumps({'report': args.output.name, 'audio': report['audio']['status'],
                      'scene_study': 'scene_study' in report}))


if __name__ == '__main__':
    main()
