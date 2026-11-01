"""Smart crop → keyframe posisi crop horizontal yang halus.

Urutan prioritas per sampel frame:
  1. Satu wajah            → ikuti wajah itu.
  2. Dua wajah atau lebih  → ikuti PEMBICARA AKTIF (gerakan area mulut paling tinggi),
                             dengan histeresis agar kamera tidak bolak-balik.
  3. Tidak ada wajah       → ikuti pusat GERAKAN (gameplay, produk, olahraga).
  4. Tidak ada gerakan     → tahan posisi terakhir.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .config import FFMPEG
from .media import _NO_WINDOW

SAMPLE_FPS = 4.0
_W = 480
# Dua wajah dianggap tampil "bersamaan" (satu bingkai, mis. panggilan video atau two-shot) bila ada di sedikitnya
# separuh sampel. Podcast hasil edit memotong bergantian antar pembicara: dua wajah stabil tetapi tidak pernah bersama.
TOGETHER = 0.5
# Presenter tunggal yang wilayahnya (kepala sampai bahu) lebih tinggi dari ini dianggap mengisi frame.
# ponytail: 0,6 dikalibrasi pada satu wawancara WIRED (tinggi 0,75); naikkan/turunkan setelah ada lebih banyak video uji.
PRESENTER_MAX_HEIGHT = 0.6


YUNET = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


class _Detector:
    """YuNet (akurat, dengan titik mulut) bila tersedia; cadangan Haar cascade."""

    def __init__(self, w: int, h: int):
        import cv2

        self.cv2 = cv2
        self.yunet = None
        if YUNET.is_file() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.75, 0.3, 50)
            except Exception as e:  # noqa: BLE001
                print(f"[smart crop] YuNet gagal dimuat ({e}); pakai Haar")
        if self.yunet is None:
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if self.haar.empty():
                raise RuntimeError("detektor wajah tidak tersedia")

    def __call__(self, gray: np.ndarray) -> list[tuple[int, int, int, int, tuple | None]]:
        """[(x, y, w, h, mouth_box|None)] dalam piksel."""
        h = gray.shape[0]
        if self.yunet is not None:
            _, faces = self.yunet.detect(self.cv2.cvtColor(gray, self.cv2.COLOR_GRAY2BGR))
            out = []
            for f in faces if faces is not None else []:
                x, y, w, hh = (int(v) for v in f[:4])
                rmx, rmy, lmx, lmy = f[10], f[11], f[12], f[13]  # sudut mulut kanan & kiri
                mw = max(abs(lmx - rmx), w * 0.25)
                cx, cy = (rmx + lmx) / 2, (rmy + lmy) / 2
                mouth = (int(cx - mw * 0.7), int(cy - mw * 0.45), int(cx + mw * 0.7), int(cy + mw * 0.55))
                out.append((max(x, 0), max(y, 0), w, hh, mouth))
            return out
        faces = self.haar.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=6, minSize=(max(h // 14, 16),) * 2)
        return [(int(x), int(y), int(w), int(hh), None) for x, y, w, hh in faces]


def _frames(src: Path, start: float, end: float, src_w: int, src_h: int) -> np.ndarray:
    h = int(round(_W * src_h / src_w / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
           "-vf", f"fps={SAMPLE_FPS},scale={_W}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    n = buf.size // (_W * h)
    return buf[: n * _W * h].reshape(n, h, _W) if n else np.zeros((0, h, _W), np.uint8)


def analyse(frames: np.ndarray) -> list[dict]:
    """Per frame: {"faces": [(cx, w, mouth_act)], "motion": cx|None, "boxes": [(cx, cy, w, h)]} — pecahan frame."""
    n, h, w = frames.shape
    det = _Detector(w, h)
    out = []
    prev = None
    for f in frames:
        diff = np.abs(f.astype(np.int16) - prev.astype(np.int16)) if prev is not None else None
        items = []
        boxes = []
        for x, y, fw, fh, mouth in det(f):
            boxes.append(((x + fw / 2) / w, (y + fh / 2) / h, fw / w, fh / h))
            act = 0.0
            if diff is not None:
                if mouth:
                    mx0, my0, mx1, my1 = (max(v, 0) for v in mouth)
                else:  # Haar: perkiraan area mulut ≈ 40% bawah kotak wajah
                    my0, my1 = y + int(fh * 0.62), y + int(fh * 1.05)
                    mx0, mx1 = x + int(fw * 0.2), x + int(fw * 0.8)
                region = diff[my0:min(my1, h), mx0:min(mx1, w)]
                # kurangi gerak kepala/kamera: bandingkan dengan area dahi
                fore = diff[y + int(fh * 0.08):y + int(fh * 0.3), x + int(fw * 0.25):x + int(fw * 0.75)]
                act = max(float(region.mean()) - float(fore.mean() if fore.size else 0), 0.0) if region.size else 0.0
            items.append(((x + fw / 2) / w, fw / w, act))
        motion = None
        if diff is not None and not items:
            col = (diff > 18).sum(axis=0).astype(np.float32)
            total = col.sum()
            if total > h * w * 0.004:  # cukup banyak piksel bergerak
                motion = float((col * np.arange(w)).sum() / total / w)
        out.append({"faces": items, "motion": motion, "boxes": boxes})
        prev = f
    return out


def choose_targets(info: list[dict], switch_ratio: float = 1.4, hold: int = 3) -> list[float | None]:
    """Pilih target x per frame. Melacak 'track' wajah berdasar posisi, memilih pembicara aktif."""
    tracks: list[dict] = []          # {x, ema, seen}
    current: dict | None = None
    challenger, streak = None, 0
    xs: list[float | None] = []
    for i, fr in enumerate(info):
        for t in tracks:
            t["ema"] *= 0.7  # rata-rata bergerak: ~2 dtk memori aktivitas mulut
        visible = []
        for cx, fw, act in fr["faces"]:
            tr = min(tracks, key=lambda t: abs(t["x"] - cx), default=None)
            if tr is None or abs(tr["x"] - cx) > max(0.12, fw * 0.8):
                tr = {"x": cx, "ema": 0.0, "seen": i}
                tracks.append(tr)
            tr["x"] = tr["x"] * 0.5 + cx * 0.5
            tr["ema"] = tr["ema"] + 0.3 * act
            tr["seen"] = i
            visible.append(tr)
        tracks = [t for t in tracks if i - t["seen"] < SAMPLE_FPS * 3]  # lupakan wajah yang hilang > 3 dtk
        if current is not None and current not in tracks:
            current = None
        if not visible and current is None:
            xs.append(fr["motion"])
            continue
        # kandidat = wajah yang terlihat dalam 1,5 detik terakhir (deteksi wajah kecil sering putus-putus)
        recent = [t for t in tracks if i - t["seen"] <= SAMPLE_FPS * 1.5]
        if len(recent) <= 1:
            if recent:
                current, challenger, streak = recent[0], None, 0
        else:
            best = max(recent, key=lambda t: t["ema"])
            if current is None or current not in recent:
                current, challenger, streak = best, None, 0
            elif best is not current and best["ema"] > current["ema"] * switch_ratio + 0.05:
                streak = streak + 1 if challenger is best else 1
                challenger = best
                if streak >= hold:
                    current, challenger, streak = best, None, 0
            else:
                challenger, streak = None, 0
        xs.append(current["x"])
    return xs


def tracking_result(src: Path, start: float, end: float, src_w: int, src_h: int, frames=None, info=None) -> dict:
    """Lacak titik fokus dan sertakan bukti/confidence untuk audit framing.

    Konsepnya mengambil pelajaran yang relevan dari ff-tracking: fokus kamera mengikuti
    target deterministik dan jalur tracking diekspor sebagai data. Berbeda dari proyek
    tersebut, footage nyata tidak memiliki koordinat glyph yang sudah diketahui, sehingga
    Clipper memakai deteksi wajah, aktivitas mulut, gerakan, smoothing, dan fallback tengah.
    """
    if frames is None:
        frames = _frames(src, start, end, src_w, src_h)
    if len(frames) == 0:
        return {"keys": [[0.0, 0.5]], "confidence": 0.0, "source": "center-fallback",
                "samples": 0, "face_samples": 0, "motion_samples": 0, "target_samples": 0}
    try:
        if info is None:
            info = analyse(frames)
    except Exception as e:  # noqa: BLE001 — OpenCV tanpa modul deteksi → crop tengah, render tetap jalan
        print(f"[smart crop] detektor wajah tidak tersedia ({e}); pakai crop tengah")
        return {"keys": [[0.0, 0.5]], "confidence": 0.0, "source": "center-fallback",
                "samples": len(frames), "face_samples": 0, "motion_samples": 0, "target_samples": 0}

    targets = choose_targets(info)
    keys = smooth(targets, src_w, src_h)
    total = max(len(info), 1)
    face_samples = sum(bool(frame["faces"]) for frame in info)
    motion_samples = sum(frame["motion"] is not None for frame in info)
    target_samples = sum(target is not None for target in targets)
    face_ratio = face_samples / total
    motion_ratio = motion_samples / total
    target_ratio = target_samples / total
    if face_samples:
        source = "active-speaker" if any(len(frame["faces"]) > 1 for frame in info) else "face"
        confidence = 0.55 * face_ratio + 0.35 * target_ratio + 0.10
    elif motion_samples:
        source = "motion"
        confidence = 0.55 * motion_ratio + 0.25 * target_ratio
    else:
        source = "center-fallback"
        confidence = 0.0
    return {"keys": keys, "confidence": round(min(max(confidence, 0.0), 1.0), 3), "source": source,
            "samples": len(info), "face_samples": face_samples, "motion_samples": motion_samples,
            "target_samples": target_samples}


def track(src: Path, start: float, end: float, src_w: int, src_h: int) -> list[list[float]]:
    """Kompatibilitas API lama: kembalikan keyframe saja."""
    return tracking_result(src, start, end, src_w, src_h)["keys"]


def smooth(xs: list[float | None], src_w: int, src_h: int) -> list[list[float]]:
    """Isi celah, median filter, lalu 'dead zone' agar kamera tidak goyang."""
    known = [x for x in xs if x is not None]
    if not known:
        return [[0.0, 0.5]]
    filled, last = [], known[0]
    for x in xs:
        last = x if x is not None else last
        filled.append(last)
    arr = np.array(filled)
    k = 7
    pad = np.pad(arr, (k // 2, k // 2), mode="edge")
    med = np.array([np.median(pad[i:i + k]) for i in range(arr.size)])

    crop_frac = min(src_h * 9 / 16 / src_w, 1.0)  # lebar crop 9:16 relatif lebar sumber
    dead = crop_frac * 0.18
    keys = [[0.0, float(med[0])]]
    cur = med[0]
    for i, x in enumerate(med[1:], 1):
        if abs(x - cur) > dead:
            t = i / SAMPLE_FPS
            jump = abs(x - cur) > crop_frac * 0.9  # ganti pembicara → potong langsung, bukan geser
            keys.append([max(t - (0.04 if jump else 0.6), keys[-1][0] + 0.02), float(cur)])
            keys.append([t, float(x)])
            cur = x
    return [[round(t, 2), round(x, 4)] for t, x in keys]


def x_expr(keys: list[list[float]], src_w: int, crop_w: int, hold: bool = False) -> str:
    """Ekspresi ffmpeg posisi x crop (pixel), dibatasi tepi frame.

    hold=False: piecewise-linear (kamera bergeser halus). hold=True: tiap keyframe menahan framing sampai keyframe
    berikutnya (tanpa drifting) — dipakai untuk keyframe manual dari Crop studio.
    """
    def px(cx):
        return max(0.0, min(src_w - crop_w, cx * src_w - crop_w / 2))

    keys = sorted(keys, key=lambda k: k[0]) or [[0, 0.5]]
    expr = f"{px(keys[-1][1]):.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(keys, keys[1:]))):
        a, b = px(x0), px(x1)
        seg = f"{a:.1f}" if hold else f"{a:.1f}+({b - a:.1f})*(t-{t0:.2f})/{max(t1 - t0, 0.01):.2f}"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    return f"if(lt(t,{keys[0][0]:.2f}),{px(keys[0][1]):.1f},{expr})"


def multi_person_frames(frames: list[np.ndarray], min_faces: int = 2) -> float:
    """Pecahan frame yang berisi >= `min_faces` wajah berukuran sebanding (panel/podcast/wawancara, bukan facecam).

    Facecam streamer selalu satu wajah kecil di sudut. Dua wajah atau lebih berukuran serupa di satu frame berarti
    orang-orang di dalam adegan (panggung, meja panel), jadi frame itu tidak boleh dianggap gameplay + facecam.
    """
    if not frames:
        return 0.0
    import cv2

    det, size, hits = None, None, 0
    for fr in frames:
        g = fr if fr.ndim == 2 else cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        h0, w0 = g.shape
        g = cv2.resize(g, (960, max(2, int(h0 * 960 / w0))))
        try:
            if det is None or size != g.shape:
                det, size = _Detector(g.shape[1], g.shape[0]), g.shape
                if getattr(det, "yunet", None) is not None:
                    det.yunet.setScoreThreshold(0.6)
            faces = det(g)
        except Exception:  # noqa: BLE001
            return 0.0
        widths = sorted((f[2] for f in faces if f[2] / g.shape[1] >= 0.02), reverse=True)
        if len(widths) >= min_faces and widths[1] >= 0.5 * widths[0]:
            hits += 1
    return hits / len(frames)


def detect_facecam(frames: list[np.ndarray]) -> dict:
    """Cari facecam di video gaming dari beberapa frame (BGR/gray).

    Hasil: {"rect": [x, y, w, h] pecahan | None, "big_face": bool, "hits": n}. Facecam = wajah kecil (<30% lebar)
    yang muncul di posisi hampir sama pada sebagian sampel. Wajah besar = video kamera biasa (podcast/vlog).
    Wajah karakter game (di tengah layar, berpindah-pindah) tidak membentuk kluster stabil sehingga diabaikan;
    kluster di sudut/tepi layar diutamakan karena posisi facecam streamer hampir selalu di sana.
    """
    if not frames:
        return {"rect": None, "big_face": False, "hits": 0}
    import cv2

    small, big = [], 0
    det, det_size = None, None
    for fr in frames:
        g = fr if fr.ndim == 2 else cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        h0, w0 = g.shape
        scale = 960 / w0          # facecam kecil lebih mudah terdeteksi bila frame diperbesar
        g = cv2.resize(g, (960, max(2, int(h0 * scale))))
        try:
            if det is None or det_size != g.shape:   # model wajah dimuat sekali per ukuran frame
                det, det_size = _Detector(g.shape[1], g.shape[0]), g.shape
                if hasattr(det, "yunet") and det.yunet is not None:
                    det.yunet.setScoreThreshold(0.6)
            faces = det(g)
        except Exception:  # noqa: BLE001
            return {"rect": None, "big_face": False, "hits": 0}
        W, H = g.shape[1], g.shape[0]
        for x, y, w, h, _ in faces:
            if w / W >= 0.30:
                big += 1
            else:
                small.append((x / W, y / H, w / W, h / H))
    n = len(frames)
    if big >= n / 2:
        return {"rect": None, "big_face": True, "hits": big}
    need = max(2, n / 3)
    if len(small) < need:
        return {"rect": None, "big_face": False, "hits": len(small)}
    centers = [(s[0] + s[2] / 2, s[1] + s[3] / 2) for s in small]

    def edge_bonus(cx, cy):   # 0..1 : makin dekat sudut/tepi makin besar
        return max(abs(cx - .5), abs(cy - .5)) * 2

    best, best_key = [], (-1, -1.0)
    for i, (cx, cy) in enumerate(centers):    # kluster terpadat (bukan median semua wajah)
        members = [small[j] for j, (qx, qy) in enumerate(centers) if abs(qx - cx) < 0.07 and abs(qy - cy) < 0.07]
        key = (len(members), edge_bonus(cx, cy))
        if key > best_key:
            best, best_key = members, key
    if len(best) < need:
        return {"rect": None, "big_face": False, "hits": len(best)}
    cx = float(np.median([s[0] + s[2] / 2 for s in best])); cy = float(np.median([s[1] + s[3] / 2 for s in best]))
    if not ((cx < .3 or cx > .7) and (cy < .3 or cy > .7)):
        # facecam streamer selalu menempel di sudut layar. Wajah kecil di tengah (mis. podcast dua orang
        # dari kamera lebar) bukan facecam, jadi jangan pernah memicu split.
        return {"rect": None, "big_face": False, "hits": len(best)}
    fw, fh = float(np.median([s[2] for s in best])), float(np.median([s[3] for s in best]))
    w, h = min(1.0, fw * 3.8), min(1.0, fh * 2.1)          # kotak facecam ≈ 3,8× lebar & 2,1× tinggi wajah
    x = float(min(max(cx - w / 2, 0), 1 - w)); y = float(min(max(cy - h / 2, 0), 1 - h))
    # facecam hampir selalu menempel ke salah satu sudut: rapatkan ke tepi terdekat (kiri/kanan/atas/bawah)
    if x < 0.06: w, x = w + x, 0.0
    if x + w > 0.94: w = 1.0 - x
    if y < 0.06: h, y = h + y, 0.0
    if y + h > 0.9: h = 1.0 - y
    return {"rect": [round(x, 4), round(y, 4), round(w, 4), round(h, 4)], "big_face": False, "hits": len(best)}


def split_areas(face: list[float], max_side: float = 0.45) -> dict:
    """Area split gaming dari facecam sudut: gameplay atas, facecam bawah."""
    x, y, w, h = [float(v) for v in face]
    gx0, gx1 = 0.0, 1.0
    if w <= max_side:
        if x + w / 2 < 0.5:
            gx0 = min(x + w, max_side)
        else:
            gx1 = max(x, 1.0 - max_side)
    return {"face": [round(x, 4), round(y, 4), round(w, 4), round(h, 4)],
            "game": [round(gx0, 4), 0.0, round(gx1 - gx0, 4), 1.0],
            "strategy": "gaming-facecam", "confidence": 0.9}


def detect_composition(frames: list[np.ndarray]) -> dict:
    """Deteksi region wajah stabil untuk keputusan split lintas profil.

    Region hanya diterima bila muncul konsisten pada sedikitnya sepertiga sampel. Kotak
    diperluas sampai bahu agar panel split tidak menghasilkan close-up wajah yang sempit.
    """
    if not frames:
        return {"faces": [], "confidence": 0.0, "samples": 0, "together": 0.0}
    import cv2

    detections: list[list[float]] = []
    per_frame: list[int] = []
    samples = 0
    detector = None
    detector_shape = None
    for frame in frames:
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h0, w0 = gray.shape
        scale = 960 / max(w0, 1)
        gray = cv2.resize(gray, (960, max(2, int(h0 * scale))))
        try:
            if detector is None or detector_shape != gray.shape:
                detector = _Detector(gray.shape[1], gray.shape[0])
                detector_shape = gray.shape
            found = detector(gray)
        except Exception:  # noqa: BLE001
            return {"faces": [], "confidence": 0.0, "samples": samples, "together": 0.0}
        samples += 1
        W, H = gray.shape[1], gray.shape[0]
        valid = 0
        for x, y, w, h, _ in found:
            if w / W < .045 or w / W > .48:
                continue
            detections.append([(x + w / 2) / W, (y + h / 2) / H, w / W, h / H])
            valid += 1
        per_frame.append(valid)

    need = max(2, int(np.ceil(samples / 3)))
    clusters: list[list[list[float]]] = []
    for item in detections:
        cx, cy, fw, _ = item
        cluster = next((c for c in clusters
                        if abs(np.median([v[0] for v in c]) - cx) < max(.10, fw * 1.2)
                        and abs(np.median([v[1] for v in c]) - cy) < .14), None)
        if cluster is None:
            clusters.append([item])
        else:
            cluster.append(item)

    regions = []
    for cluster in clusters:
        if len(cluster) < need:
            continue
        cx = float(np.median([v[0] for v in cluster]))
        cy = float(np.median([v[1] for v in cluster]))
        fw = float(np.median([v[2] for v in cluster]))
        fh = float(np.median([v[3] for v in cluster]))
        rw, rh = min(.72, max(.24, fw * 2.8)), min(.82, max(.34, fh * 2.35))
        rx = min(max(cx - rw / 2, 0.0), 1.0 - rw)
        ry = min(max(cy - rh * .40, 0.0), 1.0 - rh)
        regions.append({"rect": [round(rx, 4), round(ry, 4), round(rw, 4), round(rh, 4)],
                        "center": [round(cx, 4), round(cy, 4)], "hits": len(cluster),
                        "confidence": round(min(1.0, len(cluster) / max(samples, 1)), 3)})
    regions.sort(key=lambda r: (-r["confidence"], r["center"][0]))
    confidence = regions[0]["confidence"] if regions else 0.0
    together = sum(1 for n in per_frame if n >= 2) / max(len(per_frame), 1)
    return {"faces": regions[:4], "confidence": confidence, "samples": samples, "together": round(together, 3)}


def adaptive_split(profile: str, composition: dict, facecam: dict | None = None) -> dict:
    """Pilih split yang aman berdasarkan profil dan bukti visual.

    Gaming memakai facecam sudut. Podcast/interview memakai dua wajah stabil. Review,
    edukasi, dan profil umum memakai frame utuh sebagai konteks di atas dan presenter
    stabil di bawah. Bukti lemah selalu menghasilkan keputusan nonaktif.
    """
    facecam = facecam or {}
    faces = list((composition or {}).get("faces") or [])
    if profile in {"gaming", "mobile_legends"}:
        if facecam.get("rect"):
            return {"enabled": True, **split_areas(facecam["rect"]),
                    "reason": "Facecam stabil terdeteksi; gameplay dan wajah dipisahkan"}
        return {"enabled": False, "fallback": "blur", "confidence": 0.0,
                "reason": "Facecam stabil tidak terdeteksi; HUD dipertahankan utuh"}
    stable = [f for f in faces if float(f.get("confidence", 0)) >= .45]
    together = float((composition or {}).get("together", 1.0))   # data lama tanpa field ini: perilaku lama
    if profile in {"podcast", "interview"} and len(stable) >= 2 and together < TOGETHER:
        return {"enabled": False, "fallback": "portrait", "confidence": float(stable[0]["confidence"]),
                "reason": "Dua pembicara tampil bergantian (potongan kamera), bukan bersamaan; framing diputuskan per-shot"}
    if profile in {"podcast", "interview"} and len(stable) >= 2:
        pair = sorted(stable[:2], key=lambda f: f["center"][0])
        confidence = min(float(pair[0]["confidence"]), float(pair[1]["confidence"]))
        return {"enabled": True, "game": pair[0]["rect"], "face": pair[1]["rect"],
                "face_ratio": .48, "strategy": "dual-speaker", "confidence": round(confidence, 3),
                "reason": "Dua pembicara stabil terdeteksi; masing-masing mendapat panel sendiri"}
    if profile in {"review", "tech_review", "educational", "general"} and len(stable) >= 2:
        # Panel/meja banyak orang: panel statis akan terkunci ke satu orang saja; framing per-shot yang memilih pembicara.
        return {"enabled": False, "fallback": "portrait", "confidence": float(stable[0]["confidence"]),
                "reason": "Beberapa orang tampil di frame; framing diputuskan per-shot, bukan panel statis"}
    if profile in {"review", "tech_review", "educational", "general"} and stable:
        presenter = stable[0]
        if float(presenter["rect"][3]) > PRESENTER_MAX_HEIGHT:
            # Presenter mengisi frame: panel konteks di atas akan menampilkan orang yang sama, dan panel bawah memotongnya
            # jadi close-up dahi/mata. Crop 9:16 yang mengikuti wajah lebih baik.
            return {"enabled": False, "fallback": "portrait", "confidence": float(presenter["confidence"]),
                    "reason": "Presenter mengisi frame; crop wajah penuh dipakai agar orang yang sama tidak dobel"}
        return {"enabled": True, "game": [0.0, 0.0, 1.0, 1.0], "face": presenter["rect"],
                "face_ratio": .34, "strategy": "context-presenter",
                "confidence": presenter["confidence"],
                "reason": "Konteks visual dipertahankan di atas dan presenter stabil ditempatkan di bawah"}
    return {"enabled": False, "fallback": "portrait", "confidence": float((composition or {}).get("confidence", 0)),
            "reason": "Komposisi belum cukup stabil untuk split presisi"}
