"""Measure generated spoken-caption pixels using the renderer's libass/fonts.

Every frame is inspected, including outline, glow, animated scaling and box layers.
An explicit overlay mode also measures generated ASS title/CTA/text watermark.
Source burned-in text and image decorations remain outside this scope.
"""
from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path

from .config import FFMPEG, FONTS_DIR
from .media import _NO_WINDOW


def measure(ass: Path, width: int, height: int, duration: float, fps: float, include_overlays: bool = False) -> dict:
    if not all(math.isfinite(v) and v > 0 for v in (width, height, duration, fps)):
        raise ValueError("Invalid frame geometry")
    if width > 8192 or height > 8192 or duration > 601 or fps > 60:
        raise ValueError("Geometry exceeds supported export profile")
    # Retain only generated spoken captions, including highlight/glow layers.
    lines, events = [], 0
    for line in ass.read_text('utf-8').splitlines():
        if line.startswith('Dialogue:'):
            fields = line.split(',', 9)
            if len(fields) != 10:
                return {'method':'libass_alpha_bbox_all_frames','scope':'generated_ass_text' if include_overlays else 'generated_spoken_caption',
                        'width':width,'height':height,'fps':fps,'status':'unmeasured','bounds':None,'reason':'Malformed ASS event'}
            if not include_overlays and fields[3] not in {'Cap', 'CapBox'}:
                continue
            events += 1
        lines.append(line)
    base = {'method': 'libass_alpha_bbox_all_frames', 'scope': 'generated_ass_text' if include_overlays else 'generated_spoken_caption',
            'exclusions':['source_burned_in_text','image_watermarks','image_decorations'],
            'width': width, 'height': height, 'fps': fps}
    if not events:
        return {**base, 'status': 'not_required', 'bounds': None, 'frames': 0}
    with tempfile.TemporaryDirectory(prefix='caption-mask-') as folder:
        (Path(folder) / 'mask.ass').write_text('\n'.join(lines) + '\n', 'utf-8')
        fonts = str(FONTS_DIR.resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
        filters = f"ass=filename=mask.ass:fontsdir='{fonts}':alpha=1,alphaextract,bbox=min_val=1"
        result = subprocess.run([FFMPEG, '-hide_banner', '-nostdin', '-f', 'lavfi', '-i',
                                 f'color=c=black@0:s={int(width)}x{int(height)}:r={fps}:d={duration},format=rgba',
                                 '-vf', filters, '-an', '-f', 'null', '-'], cwd=folder,
                                capture_output=True, timeout=300, creationflags=_NO_WINDOW)
    log = result.stderr.decode('utf-8', 'replace')
    if result.returncode:
        return {**base, 'status': 'unmeasured', 'bounds': None, 'reason': 'Caption mask rendering failed'}
    frames = [int(n) for n in re.findall(r'\bn:(\d+) pts:', log)]
    boxes = [tuple(map(int, b)) for b in re.findall(r'\bx1:(\d+) x2:(\d+) y1:(\d+) y2:(\d+)', log)]
    measured_frames = max(frames, default=-1) + 1
    if measured_frames < math.ceil(duration * fps - 1e-6) or not boxes:
        return {**base, 'status': 'unmeasured', 'bounds': None, 'frames': measured_frames,
                'reason': 'Caption pixels or complete frame coverage could not be measured'}
    return {**base, 'status': 'measured', 'frames': measured_frames,
            'bounds': {'left': min(b[0] for b in boxes), 'right': max(b[1] for b in boxes) + 1,
                       'top': min(b[2] for b in boxes), 'bottom': max(b[3] for b in boxes) + 1}}


def evaluate(measured: dict, margins: dict) -> dict:
    width, height = measured['width'], measured['height']
    zone = {'left': math.ceil(width * margins['left']), 'right': math.floor(width * (1 - margins['right'])),
            'top': math.ceil(height * margins['top']), 'bottom': math.floor(height * (1 - margins['bottom']))}
    bounds = measured.get('bounds')
    if measured['status'] == 'not_required':
        return {**measured, 'ok': True, 'safe_zone': zone, 'issues': []}
    if measured['status'] != 'measured' or not bounds:
        return {**measured, 'ok': False, 'safe_zone': zone,
                'issues': ['Zona aman teks belum dapat diukur; render ulang lalu coba lagi.']}
    inside = bounds['left'] >= zone['left'] and bounds['right'] <= zone['right'] and bounds['top'] >= zone['top'] and bounds['bottom'] <= zone['bottom']
    return {**measured, 'ok': inside, 'safe_zone': zone,
            'issues': [] if inside else ['Teks keluar zona aman profil ini. Geser/perkecil caption, judul, CTA atau watermark teks lalu render ulang.']}
