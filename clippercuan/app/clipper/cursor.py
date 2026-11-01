"""Conservative motion/shape cursor tracking, explicitly limited to screen recordings."""
from __future__ import annotations

import cv2
import numpy as np
from . import facetrack


def track(frames: np.ndarray, src_w: int, src_h: int) -> dict:
    xs, accepted, previous = [], 0, None
    for frame in frames:
        candidate = None
        if previous is not None:
            delta = cv2.absdiff(frame, previous)
            mask = ((delta > 30) & (frame > 190)).astype(np.uint8)
            count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
            options = []
            for i in range(1, count):
                x, y, w, h, area = stats[i]
                if 3 <= w <= max(14, frame.shape[1] * .045) and 4 <= h <= max(20, frame.shape[0] * .08) and 5 <= area <= 150 and .2 <= w / h <= 1.4:
                    options.append((area, float(centers[i][0]) / frame.shape[1]))
            # Competing bright moving components imply uncertainty, not a cursor.
            if len(options) == 1: candidate = options[0][1]; accepted += 1
        xs.append(candidate)
        previous = frame
    confidence = accepted / max(1, len(frames) - 1)
    return {'keys': facetrack.smooth(xs, src_w, src_h) if confidence >= .6 else None,
            'confidence': round(confidence, 3), 'source': 'cursor_motion_shape_heuristic',
            'samples': len(frames), 'fallback': confidence < .6, 'benchmark': 'synthetic_only'}
