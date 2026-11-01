"""Framing per-shot untuk klip dari video 16:9 (podcast, wawancara, video edukasi).

Video hasil edit memotong antar-shot: satu orang, orang lain, dua orang bersamaan, B-roll. Satu jalur kamera
yang dihaluskan lintas potongan membuat framing tertinggal sekitar satu detik setelah tiap cut (wajah terpotong).
Di sini setiap shot diputuskan sendiri:

  single  satu wajah        → crop 9:16 mengikuti wajah, pelacak di-reset di awal shot
  multi   dua wajah bersama → dua panel bertumpuk, masing-masing memusatkan satu orang
  broll   tanpa wajah       → frame utuh di tengah + latar blur (foto, tangkapan layar, arsip)

Modul ini hanya menganalisis. Penyusunan filter ffmpeg ada di render.py.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

from . import facetrack
from .config import FFMPEG
from .media import _NO_WINDOW

# ponytail: ambang dikalibrasi pada satu wawancara WIRED (1080p, 23,98 fps, 17 cut/menit); setel ulang dengan lebih banyak video.
FACE_TARGET = 0.42         # target lebar wajah di panel output (pecahan); shot lebar di-zoom sampai mendekati ini
MAX_SHOT_ZOOM = 2.2        # batas zoom per shot agar tidak terlalu pecah/lembek
SCENE_THRESHOLD = 0.30     # skor ffmpeg `scene`; lebih rendah = lebih sensitif
SOFT_FLOOR = 0.015         # event di bawah ini diabaikan; di atasnya dikumpulkan untuk mendeteksi dissolve/crossfade
SOFT_SUM = 0.35            # total skor satu kelompok event agar dihitung satu transisi lembut
SOFT_PEAK = 0.02           # dan puncaknya minimal ini (gerak tangan/kepala biasanya < 0.02)
CLUSTER_GAP = 0.4          # jeda antar event yang masih satu kelompok
CLUSTER_SPAN = 3.0         # kelompok lebih panjang dari ini dipecah
MIN_SHOT = 0.35            # shot lebih pendek dari ini digabung ke tetangganya
MIN_PIECE = 0.1            # irisan lebih pendek dari ini digabung agar trim tidak menghasilkan nol frame
MIN_FACE = 0.04            # lebar wajah minimum (pecahan lebar frame) agar dihitung
MIN_FACE_SHARE = 0.4       # shot "single" bila wajah terlihat di sedikitnya 40% sampel


def cuts_from_events(events: list[tuple[float, float]], hard: float = SCENE_THRESHOLD) -> list[float]:
    """(waktu, skor scene) → waktu potongan. Skor besar = potong keras; kelompok skor kecil yang rapat dan kuat = dissolve.

    Video panel/wawancara sering berganti sudut kamera lewat crossfade ~1 detik: skornya hanya 0.02-0.06 per frame
    sehingga ambang 0.30 tidak melihatnya, dan framing satu shot dipakai untuk dua sudut kamera yang berbeda.
    """
    cuts: list[float] = []
    group: list[tuple[float, float]] = []

    def close() -> None:
        if not group:
            return
        top = max(group, key=lambda e: e[1])
        if top[1] > hard:
            cuts.append(top[0])
        elif sum(s for _, s in group) >= SOFT_SUM and top[1] >= SOFT_PEAK:
            cuts.append((group[0][0] + group[-1][0]) / 2)
        group.clear()

    for t, s in sorted(events):
        if group and (t - group[-1][0] > CLUSTER_GAP or t - group[0][0] > CLUSTER_SPAN):
            close()
        group.append((t, s))
    close()
    return cuts


def detect_cuts(src: Path, start: float, end: float, threshold: float = SCENE_THRESHOLD) -> list[float]:
    """Waktu potongan kamera (detik, relatif awal klip), termasuk transisi dissolve."""
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
           "-vf", f"scale=320:-2,select='gt(scene,{min(threshold, SOFT_FLOOR)})',metadata=print:file=-",
           "-an", "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW).stdout.decode("utf-8", "replace")
    times = re.findall(r"pts_time:([0-9.]+)", out)
    scores = re.findall(r"lavfi\.scene_score=([0-9.]+)", out)
    return cuts_from_events([(float(t), float(s)) for t, s in zip(times, scores)], hard=threshold)


def boundaries(cuts: list[float], duration: float, min_shot: float = MIN_SHOT) -> list[tuple[float, float]]:
    """Rentang shot yang menutup [0, duration] tanpa celah; shot terlalu pendek digabung."""
    if duration <= 0:
        return []
    edges = [0.0]
    for c in cuts:
        if c - edges[-1] >= min_shot and duration - c >= min_shot:
            edges.append(c)
    edges.append(duration)
    return [(round(a, 3), round(b, 3)) for a, b in zip(edges, edges[1:])]


def classify(info: list[dict], a: float, b: float, src_w: int, src_h: int) -> dict:
    """Putuskan mode satu shot dari sampel deteksi wajah di dalam [a, b)."""
    idx = [i for i in range(len(info)) if a <= i / facetrack.SAMPLE_FPS < b]
    if not idx and info:      # shot lebih pendek dari satu sampel: pakai sampel terdekat
        idx = [min(int(a * facetrack.SAMPLE_FPS), len(info) - 1)]
    seg = [info[i] for i in idx]
    if not seg:
        return {"a": a, "b": b, "mode": "broll", "confidence": 0.0}

    big = [[bx for bx in fr.get("boxes", []) if bx[2] >= MIN_FACE] for fr in seg]
    both = [bs for bs in big if len(bs) >= 2]
    if len(both) / len(seg) >= facetrack.TOGETHER:
        left, right = [], []
        for bs in both:
            two = sorted(sorted(bs, key=lambda bx: -bx[2])[:2], key=lambda bx: bx[0])
            left.append(two[0])
            right.append(two[1])
        faces = [[round(float(v), 4) for v in np.median(np.array(side), axis=0)] for side in (left, right)]
        return {"a": a, "b": b, "mode": "multi", "faces": faces, "confidence": round(len(both) / len(seg), 3)}

    with_face = [fr for fr in seg if fr["faces"]]
    if len(with_face) / len(seg) >= MIN_FACE_SHARE:
        targets = facetrack.choose_targets(seg)
        keys = facetrack.smooth(targets, src_w, src_h)
        face_ratio = len(with_face) / len(seg)
        target_ratio = sum(t is not None for t in targets) / len(seg)
        conf = min(1.0, 0.55 * face_ratio + 0.35 * target_ratio + 0.10)
        zoom, cy = framing_zoom([bx for bs in big for bx in bs], src_w, src_h)
        return {"a": a, "b": b, "mode": "single", "keys": keys, "confidence": round(conf, 3), "zoom": zoom, "cy": cy}
    return {"a": a, "b": b, "mode": "broll", "confidence": 0.8}


def framing_zoom(boxes: list[tuple], src_w: int, src_h: int, ar: float = 9 / 16) -> tuple[float, float]:
    """(zoom, pusat-y wajah) untuk satu shot dari kotak wajah (cx, cy, w, h pecahan frame).

    Lebar wajah di panel = fw·W·z / (H·ar). Shot dekat (wajah sudah besar) tidak di-zoom; shot lebar di-zoom
    sampai wajah ≈ FACE_TARGET lebar panel. Pusat-y diambil dari median wajah agar kepala tetap di bingkai.
    """
    if not boxes:
        return 1.0, 0.4
    fw = float(np.median([bx[2] for bx in boxes]))
    cy = float(np.median([bx[1] for bx in boxes]))
    zoom = FACE_TARGET * src_h * ar / max(fw * src_w, 1e-6)
    return round(min(max(zoom, 1.0), MAX_SHOT_ZOOM), 3), round(cy, 4)


def plan(src: Path, start: float, end: float, src_w: int, src_h: int, duration: float | None = None,
         frames=None, info=None, cuts: list[float] | None = None) -> dict | None:
    """Rencana framing per shot untuk klip [start, end]. None bila deteksi tidak tersedia (pakai jalur lama)."""
    dur = duration if duration is not None else max(end - start, 0.5)
    if frames is None:
        frames = facetrack._frames(src, start, end, src_w, src_h)
    if len(frames) == 0:
        return None
    if info is None:
        info = facetrack.analyse(frames)
    if cuts is None:
        cuts = detect_cuts(src, start, end)
    shots = [classify(info, a, b, src_w, src_h) for a, b in boundaries(cuts, dur)]
    if not shots:
        return None
    total = sum(s["b"] - s["a"] for s in shots) or 1.0
    confidence = sum(s["confidence"] * (s["b"] - s["a"]) for s in shots) / total
    return {"shots": shots, "confidence": round(confidence, 3), "source": "shots", "cuts": len(shots) - 1,
            "samples": len(info), "face_samples": sum(bool(fr["faces"]) for fr in info),
            "multi_shots": sum(s["mode"] == "multi" for s in shots)}


def shift_keys(keys: list[list[float]] | None, offset: float) -> list[list[float]] | None:
    """Geser keyframe shot ke awal potongan yang lebih lambat (mis. setelah potong jeda hening)."""
    if not keys or offset <= 0.001:
        return keys
    shifted = [[round(t - offset, 2), x] for t, x in keys if t - offset > 0.001]
    before = [x for t, x in keys if t - offset <= 0.001]
    return [[0.0, before[-1] if before else keys[0][1]]] + shifted


def pieces(shots: list[dict], keep: list[tuple[float, float]], min_piece: float = MIN_PIECE) -> list[dict]:
    """Irisan shot dengan rentang yang dipertahankan (potong jeda). Tanpa potong: keep = [(0, durasi)].

    Irisan yang sangat pendek digabung ke tetangga yang bersambung (bukan dibuang), supaya total durasi video
    sama dengan total rentang audio yang dipertahankan.
    """
    raw = []
    for ka, kb in keep:
        for s in shots:
            a, b = max(ka, s["a"]), min(kb, s["b"])
            if b - a > 1e-3:
                raw.append({**s, "a": a, "b": b, "sa": s["a"]})
    merged: list[dict] = []
    for sl in raw:                                   # irisan pendek → perpanjang irisan sebelumnya
        if merged and sl["b"] - sl["a"] < min_piece and abs(merged[-1]["b"] - sl["a"]) < 1e-3:
            merged[-1]["b"] = sl["b"]
        else:
            merged.append(sl)
    out: list[dict] = []
    for i, sl in enumerate(merged):                  # irisan pendek di awal → tarik irisan berikutnya mundur
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        if sl["b"] - sl["a"] < min_piece and nxt is not None and abs(sl["b"] - nxt["a"]) < 1e-3:
            nxt["a"] = sl["a"]
        else:
            out.append(sl)
    for sl in out:
        sl["keys"] = shift_keys(sl.get("keys"), max(0.0, sl["a"] - sl["sa"]))
    return out
