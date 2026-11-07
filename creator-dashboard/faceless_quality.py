"""Non-blocking editorial preflight for narrated faceless videos.

This intentionally does not rate cinematic quality: it detects a few structural
conditions that commonly produce unwatchable, repetitive slideshow renders.
Human review and real frame/audio inspection remain mandatory.
"""
from __future__ import annotations

from collections import Counter


ABSTRACT = frozenset({"concept", "constellation", "portal", "kinetic-type"})
MAX_WORDS_PER_SECOND = 3.2


def inspect(plan: dict) -> dict:
    scenes = plan.get("scenes") or []
    warnings: list[dict] = []
    def warn(code: str, message: str, scene: str = ""):
        warnings.append({"code": code, "message": message, "scene": scene})

    if not scenes:
        warn("no_scenes", "Belum ada adegan. Tambahkan Scene Plan sebelum render.")
    titles = Counter()
    abstract = 0
    for scene in scenes:
        sid = str(scene.get("id", ""))
        title = str(scene.get("onScreenText", "")).strip()
        text = str(scene.get("narration", "")).strip()
        if title:
            titles[title.casefold()] += 1
        if len(title) > 76:
            warn("long_title", "Judul adegan sangat panjang; ringkas agar terbaca di layar ponsel.", sid)
        if scene.get("visualFamily") in ABSTRACT and not scene.get("diagram"):
            abstract += 1
        length = float(scene.get("end", 0)) - float(scene.get("start", 0))
        if length > 0 and len(text.split()) / length > MAX_WORDS_PER_SECOND:
            warn("dense_narration", "Narasi terlalu padat untuk durasi adegan; pecah scene atau tambah durasi.", sid)
        if length > 0 and length < 1.25:
            warn("short_scene", "Adegan kurang dari 1,25 detik; periksa waktu baca teks dan efek.", sid)

    if any(count > 1 for count in titles.values()):
        warn("duplicate_headline", "Ada judul adegan yang identik. Periksa apakah cerita terasa berulang.")
    if len(scenes) >= 4 and abstract > len(scenes) * .55:
        warn("abstract_overuse", "Sebagian besar shot memakai simbol abstrak. Ganti sebagian dengan objek/visual konkret.")
    speech = plan.get("speech")
    if speech and speech.get("mode") == "none" and any(s.get("narration") for s in scenes):
        warn("narration_disabled", "Naskah ada tetapi suara narator dimatikan. Pastikan ini memang disengaja.")
    if plan.get("audioMode") == "music" and any(s.get("narration") for s in scenes):
        warn("music_only", "Mode musik dipilih; teks narasi tidak akan didubbing.")

    return {
        "status": "needs_review" if warnings else "manual_review_required",
        "method": "structural_heuristics_not_aesthetic_review",
        "warnings": warnings,
        "manualRequired": [
            "Verifikasi keakuratan informasi dan sumber",
            "Dengarkan seluruh dubbing untuk memastikan sesuai naskah",
            "Periksa lisensi dan hak pakai semua aset sebelum monetisasi",
            "Bandingkan visual antarscene, jangan publikasikan template massal generik",
        ],
    }
