"""Efek tambahan: emoji otomatis dari kata kunci + utilitas musik latar."""
from __future__ import annotations

import re
from pathlib import Path

from .config import DATA_DIR

EMOJI_DIR = Path(__file__).resolve().parent / "emoji"
MUSIC_DIR = DATA_DIR / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# kata (awalan) → kode emoji. Bahasa Indonesia + Inggris.
_MAP = {
    "1f4b0": "uang duit cuan gaji money cash rupiah dollar",
    "1f4b8": "juta miliar boros mahal expensive",
    "1f525": "viral panas api hot fire trending",
    "1f92b": "rahasia secret diam",
    "1f631": "kaget shock terkejut wow astaga",
    "1f602": "ketawa lucu ngakak funny lol haha",
    "2764": "cinta love sayang hati heart",
    "1f622": "sedih sad nangis menangis kecewa",
    "1f621": "marah kesal angry emosi",
    "1f4a1": "ide idea tips trik solusi inspirasi",
    "23f0": "waktu jam time deadline menit",
    "1f4bc": "bisnis usaha business kantor karier karir",
    "1f3c6": "sukses berhasil juara menang success win champion",
    "274c": "gagal salah fail wrong jangan",
    "2705": "benar betul setuju berhasil correct yes",
    "2757": "penting wajib harus important must",
    "1f914": "kenapa mengapa bingung pikir why",
    "1f354": "makan makanan lapar food eat",
    "1f4bb": "kerja kerjaan laptop komputer work coding",
    "1f4da": "belajar sekolah kuliah buku study learn",
    "1f3e0": "rumah keluarga home house",
    "1f697": "mobil motor perjalanan car",
    "1f3ae": "game gaming main player",
    "1f3b5": "musik lagu music song",
    "1f3af": "target tujuan fokus goal",
    "1f4c8": "naik tumbuh untung profit growth omzet",
    "1f4c9": "turun rugi bangkrut loss",
    "1f4aa": "kuat semangat strong power",
    "26a0": "bahaya hati-hati awas danger warning",
    "1f9e0": "otak cerdas pintar mindset brain smart",
    "1f440": "lihat perhatikan see look",
    "1f381": "hadiah gratis bonus gift free",
    "2b50": "terbaik bintang best star",
    "1f680": "cepat roket meroket fast rocket",
    "1f30d": "dunia global world",
    "1f4f1": "hp handphone aplikasi phone app",
    "1f4f8": "foto kamera konten camera photo",
    "1f634": "tidur ngantuk capek sleep tired",
    "1f60e": "keren santai cool",
    "1f44d": "mantap bagus oke good",
    "1f64f": "terima kasih makasih doa thanks pray",
    "1f6d2": "jual beli belanja jualan shop buy sell",
    "1f480": "mati death mampus",
    "2615": "kopi ngopi coffee",
    "1f389": "selamat rayakan party celebrate",
    "1f92f": "gila parah mindblown crazy insane",
    "1f4af": "serius sungguh beneran seratus",
}
WORD_TO_EMOJI: dict[str, str] = {}
for code, words in _MAP.items():
    for w in words.split():
        WORD_TO_EMOJI.setdefault(w, code)

_CLEAN = re.compile(r"[^\w-]+", re.UNICODE)


def emoji_for(word: str) -> str | None:
    w = _CLEAN.sub("", word.lower())
    if len(w) < 3:
        return None
    if w in WORD_TO_EMOJI:
        return WORD_TO_EMOJI[w]
    # akhiran umum bahasa Indonesia: -nya, -kan, -an, -lah, -mu, -ku
    for suf in ("nya", "kan", "lah", "an", "mu", "ku"):
        if w.endswith(suf) and w[: -len(suf)] in WORD_TO_EMOJI:
            return WORD_TO_EMOJI[w[: -len(suf)]]
    return None


def safe_zones(profile: str, layout: str, caption_y_pct: float = 74) -> list[dict]:
    """Area terlarang ternormalisasi untuk dekorasi: caption, wajah/produk, dan HUD umum."""
    zones = [{"kind": "spoken-caption", "rect": [0.08, max(.05, caption_y_pct / 100 - .1), .84, .2]}]
    if profile in {"gaming", "mobile_legends"}:
        zones += [{"kind": "minimap", "rect": [0, 0, .3, .3]},
                  {"kind": "score", "rect": [.32, 0, .36, .16]},
                  {"kind": "controls", "rect": [.62, .62, .38, .38]},
                  {"kind": "kill-feed", "rect": [.66, .14, .34, .25]}]
    elif profile in {"review", "tech_review"}:
        zones += [{"kind": "product", "rect": [.18, .28, .64, .5]}]
    elif profile in {"podcast", "interview"}:
        zones += [{"kind": "face", "rect": [.18, .08, .64, .5]}]
    if layout == "split":
        zones.append({"kind": "facecam", "rect": [0, 0, 1, .38]})
    return zones


def _overlaps(a: list[float], b: list[float]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def decoration_layout(profile: str, layout: str, caption_y_pct: float = 74) -> dict:
    """Pilih satu posisi konservatif; nonaktif bila semua posisi berbenturan."""
    blocked = safe_zones(profile, layout, caption_y_pct)
    candidates = [("top-right", [.74, .34, .18, .18]), ("top-left", [.08, .34, .18, .18]),
                  ("center-top", [.41, .18, .18, .18])]
    for name, rect in candidates:
        collisions = [z["kind"] for z in blocked if _overlaps(rect, z["rect"])]
        if not collisions:
            return {"enabled": True, "position": name, "rect": rect, "blocked": blocked, "reason": "safe-area tersedia"}
    return {"enabled": False, "position": None, "rect": None, "blocked": blocked,
            "reason": "dekorasi dibatalkan: tidak ada area aman"}


def plan_emojis(words: list[dict], duration: float, max_count: int = 10, min_gap: float = 2.2,
                show: float = 1.3, provenance: str = "keyword") -> list[dict]:
    """Rencana semantik; interval tidak tumpang tindih dan setiap item punya provenance."""
    out: list[dict] = []
    last_t, last_code = -99.0, None
    for w in words:
        code = emoji_for(w["w"])
        if not code or w["s"] - last_t < min_gap or code == last_code:
            continue
        f = EMOJI_DIR / f"{code}.png"
        if not f.is_file():
            continue
        s = max(0.0, w["s"] - 0.05)
        e = min(s + show, duration)
        if out and s < out[-1]["e"]:
            continue
        out.append({"code": code, "s": round(s, 2), "e": round(e, 2), "file": str(f),
                    "provenance": provenance, "keyword": w["w"]})
        last_t, last_code = w["s"], code
        if len(out) >= max_count:
            break
    return out


def list_music() -> list[dict]:
    exts = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}
    return [{"name": f.stem, "file": str(f)} for f in sorted(MUSIC_DIR.iterdir()) if f.suffix.lower() in exts]
