"""Queued platform variants. Original renders are preserved; only checked variants download."""
from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from . import caption_geometry, delivery, media
from .config import FFMPEG
from .security import redact


class ExportBlocked(ValueError):
    pass


def _digest(path: Path) -> str:
    return media.file_digest(path)


def _path(folder: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ExportBlocked('Artefak tidak tersedia')
    resolved = (folder / relative).resolve()
    if not resolved.is_relative_to(folder.resolve()) or not resolved.is_file():
        raise ExportBlocked('Artefak tidak tersedia')
    return resolved


def _clip(pid: str, cid: str) -> tuple[Path, dict]:
    from . import project

    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', cid):
        raise KeyError(cid)
    p = project.load(pid)
    clip = next((c for c in p.get('clips', []) if c['id'] == cid), None)
    if clip is None:
        raise KeyError(cid)
    return project.pdir(pid), clip


def _ready(clip: dict) -> None:
    if clip.get('status') != 'done' or clip.get('needs_rerender'):
        raise ExportBlocked('Render klip terbaru sebelum ekspor per platform')


def enqueue(pid: str, cid: str, platform: str) -> dict:
    from . import project

    platform = delivery.platform_id(platform)
    with project._LOCK:
        folder, clip = _clip(pid, cid)
        _ready(clip)
        source = _path(folder, clip.get('file'))
        source_digest = _digest(source)
        if source_digest != clip.get('artifact_digest') or not clip.get('caption_ass_digest'):
            raise ExportBlocked('Metadata integritas render belum tersedia/berubah; render ulang klip sebelum ekspor')
        existing = (clip.get('exports') or {}).get(platform)
        if existing and existing['status'] in {'queued', 'processing'}:
            return copy.deepcopy(existing)
        state = {'status': 'queued', 'platform': platform, 'token': uuid.uuid4().hex,
                 'source_digest': source_digest, 'ass_digest': clip['caption_ass_digest'], 'source_version': clip.get('version'), 'updated': time.time(), 'owner': os.getpid()}
        project._set_clip(pid, cid, exports={**clip.get('exports', {}), platform: state})
        project._JOBS.put(('platform_export', pid, {'cid': cid, 'platform': platform, 'token': state['token']}))
        return copy.deepcopy(state)


def _store(pid: str, cid: str, platform: str, token: str, **values) -> bool:
    from . import project

    with project._LOCK:
        _, clip = _clip(pid, cid)
        exports = clip.get('exports') or {}
        current = exports.get(platform) or {}
        if current.get('token') != token:
            return False
        exports[platform] = {**current, **values, 'updated': time.time()}
        project._set_clip(pid, cid, exports=exports)
        return True


def _run(args: list[str], timeout: float = 1800) -> subprocess.CompletedProcess:
    result = subprocess.run([FFMPEG, '-hide_banner', '-nostdin', *args], capture_output=True,
                            timeout=timeout, creationflags=media._NO_WINDOW)
    if result.returncode:
        # No raw FFmpeg output or local paths are returned to the public API.
        raise RuntimeError('Encoder gagal membuat varian platform')
    return result


def transcode(source: Path, target: Path, platform: str, fps: float) -> None:
    spec = delivery.PLATFORMS[platform]
    common = f"I={spec['lufs']}:TP=-1:LRA=11"
    measured = _run(['-protocol_whitelist', 'file,pipe', '-i', str(source), '-vn', '-af', f'loudnorm={common}:print_format=json', '-f', 'null', '-'])
    log = measured.stderr.decode('utf-8', 'replace')
    start, end = log.rfind('{'), log.rfind('}')
    if start < 0 or end <= start:
        raise ExportBlocked('Loudness audio belum dapat diukur')
    levels = json.loads(log[start:end + 1])
    mapping = {'input_i': 'measured_I', 'input_tp': 'measured_TP', 'input_lra': 'measured_LRA',
               'input_thresh': 'measured_thresh', 'target_offset': 'offset'}
    values = {dest: float(levels[key]) for key, dest in mapping.items()}
    if not all(math.isfinite(v) for v in values.values()):
        raise ExportBlocked('Audio senyap/tidak terukur; periksa audio sebelum ekspor')
    normalization = 'loudnorm=' + common + ':' + ':'.join(f'{k}={v}' for k, v in values.items()) + ':linear=true'
    _run(['-y', '-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0', '-map_metadata', '-1', '-map_chapters', '-1',
          '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-r', str(min(fps, 60)), '-c:v', 'libx264', '-preset', 'medium',
          '-crf', '20', '-maxrate', spec['maxrate'], '-bufsize', spec['bufsize'], '-pix_fmt', 'yuv420p',
          '-af', normalization, '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', str(target)])


def process(pid: str, cid: str, platform: str, token: str) -> None:
    from . import project

    output = None
    try:
        folder, clip = _clip(pid, cid)
        state = (clip.get('exports') or {}).get(platform) or {}
        if state.get('token') != token or state.get('status') != 'queued':
            return
        _ready(clip)
        source = _path(folder, clip.get('file'))
        if _digest(source) != state['source_digest']:
            raise ExportBlocked('Render sumber telah berubah; ulangi ekspor')
        if not _store(pid, cid, platform, token, status='processing'):
            return
        pr = media.probe(source)
        if pr.duration > delivery.PLATFORMS[platform]['max_sec'] or not pr.has_audio:
            raise ExportBlocked('Durasi/audio tidak memenuhi profil platform; perbaiki klip sebelum ekspor')
        ass = _path(folder, clip.get('ass'))
        if _digest(ass) != state.get('ass_digest'):
            raise ExportBlocked('Caption berubah setelah render; render ulang sebelum ekspor')
        geometry = caption_geometry.measure(ass, pr.width, pr.height, pr.duration, min(pr.fps, 60), include_overlays=True)
        geometry = caption_geometry.evaluate(geometry, delivery.PLATFORMS[platform]['safe'])
        if not geometry['ok']:
            _store(pid, cid, platform, token, status='blocked', geometry=geometry, error=' '.join(geometry['issues']))
            return
        destination = folder / 'variants'
        destination.mkdir(exist_ok=True)
        if destination.is_symlink():
            raise ExportBlocked('Folder varian tidak valid')
        with tempfile.TemporaryDirectory(prefix='encode-', dir=destination) as temp:
            temporary = Path(temp) / 'video.mp4'
            transcode(source, temporary, platform, pr.fps)
            report = delivery.check(temporary, platform)
            # These exports promise measured loudness, unlike legacy raw downloads.
            if not report['ok'] or any(i['code'] in {'loudness', 'loudness-unmeasured'} for i in report['issues']):
                _store(pid, cid, platform, token, status='blocked', delivery=report, geometry=geometry,
                       error='Hasil encode belum lolos pemeriksaan delivery')
                return
            with project._LOCK:
                _, latest = _clip(pid, cid)
                _ready(latest)
                if latest.get('version') != state.get('source_version') or _digest(source) != state['source_digest'] or _digest(ass) != state.get('ass_digest'):
                    raise ExportBlocked('Sumber berubah selama ekspor; ulangi dari render terbaru')
                filename = f'{cid}-{platform}-{token}.mp4'
                output = destination / filename
                temporary.replace(output)
                if not _store(pid, cid, platform, token, status='passed', file=f'variants/{filename}',
                              output_digest=_digest(output), geometry=geometry, delivery=report, error=None):
                    output.unlink(missing_ok=True)
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if output is not None:
            output.unlink(missing_ok=True)
        try:
            _store(pid, cid, platform, token, status='blocked' if isinstance(exc, ExportBlocked) else 'error',
                   error=redact(str(exc))[:300])
        except KeyError:
            pass  # project/clip was deleted while working


def download(pid: str, cid: str, platform: str) -> Path:
    from . import project

    platform = delivery.platform_id(platform)
    with project._LOCK:
        folder, clip = _clip(pid, cid)
        _ready(clip)
        state = (clip.get('exports') or {}).get(platform) or {}
        if state.get('status') != 'passed':
            raise ExportBlocked('Varian platform belum lolos pemeriksaan')
        if (state.get('geometry') or {}).get('scope') != 'generated_ass_text':
            raise ExportBlocked('Pemeriksaan zona aman varian lama belum mencakup seluruh teks ASS; ulangi ekspor')
        if state.get('source_version') != clip.get('version') or _digest(_path(folder, clip.get('file'))) != state.get('source_digest'):
            raise ExportBlocked('Varian berasal dari render lama; ulangi ekspor')
        output = _path(folder, state.get('file'))
        if _digest(output) != state.get('output_digest'):
            raise ExportBlocked('Artefak berubah setelah pemeriksaan; ulangi ekspor')
        return output
