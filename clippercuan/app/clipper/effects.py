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
    "1f92f": "gila parah mindblown crazy insane anjir buset",
    "1f4af": "serius sungguh beneran seratus totalitas",
}
# Tambahan semantik Bahasa Indonesia (slang, review, podcast). Hanya kode yang aset PNG lokalnya ada.
_MAP_ID_EXTRA = {
    "1f4b0": "harga murah investasi tabungan nabung bayar",
    "1f4b8": "kemahalan overprice pricey",
    "1f525": "gacor ngegas pecah",
    "1f631": "kaget waduh lho kok",
    "1f602": "wkwk wkwkwk kocak receh",
    "1f622": "galau baper sakit",
    "1f621": "kesel sebel ngamuk",
    "1f4a1": "cara kunci rahasianya caranya",
    "1f3af": "intinya poin sasaran",
    "1f4c8": "meningkat naiknya cuan laris",
    "1f4c9": "anjlok merosot",
    "26a0": "hati awas jebakan risiko",
    "1f4f1": "smartphone gadget android iphone ponsel",
    "1f4bb": "laptop software prosesor chip",
    "1f4f8": "kamera lensa video",
    "1f50b": "baterai",
    "2b50": "rekomendasi recommended worth",
    "1f44d": "recommended mantul",
    "274c": "minus kurang zonk",
    "2705": "plus kelebihan",
    "1f914": "gimana bagaimana apakah",
    "1f60d": "suka naksir cantik ganteng",
    "1f44f": "hebat salut keren",
}
for _code, _words in _MAP_ID_EXTRA.items():
    _MAP[_code] = (_MAP.get(_code, "") + " " + _words).strip()
# Kata fungsi bebas emoji walau cocok prefiks.
_STOP = {"jangan", "harus", "main", "lihat", "waktu"}
WORD_TO_EMOJI: dict[str, str] = {}
for code, words in _MAP.items():
    if not (EMOJI_DIR / f"{code}.png").is_file():   # hanya aset lokal berlisensi
        continue
    for w in words.split():
        if w not in _STOP:
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
    # Sudut kecil di luar zona wajah/produk (x .18-.82) agar podcast/review tetap punya slot aman.
    candidates = [("top-right", [.74, .34, .18, .18]), ("top-left", [.08, .34, .18, .18]),
                  ("center-top", [.41, .18, .18, .18]),
                  ("corner-right", [.84, .12, .12, .12]), ("corner-left", [.04, .12, .12, .12])]
    for name, rect in candidates:
        collisions = [z["kind"] for z in blocked if _overlaps(rect, z["rect"])]
        if not collisions:
            return {"enabled": True, "position": name, "rect": rect, "blocked": blocked, "reason": "safe-area tersedia"}
    return {"enabled": False, "position": None, "rect": None, "blocked": blocked,
            "reason": "dekorasi dibatalkan: tidak ada area aman"}


EMOJI_IN_MS, EMOJI_OUT_MS = 240, 220   # pop/bounce singkat lalu diam, keluar fade


def plan_emojis(words: list[dict], duration: float, max_count: int = 10, min_gap: float = 2.2,
                show: float = 1.3, provenance: str = "keyword", suggestions: dict | None = None) -> list[dict]:
    """Rencana semantik; maks 1 aktif, jarak minimal min_gap antar akhir→awal, setiap item punya provenance.

    suggestions: {kata_lower: kode} dari 9Router opsional; dipakai hanya bila aset lokal ada (provenance 'llm').
    """
    out: list[dict] = []
    last_code = None
    for w in words:
        key = _CLEAN.sub("", w["w"].lower())
        code, prov = emoji_for(w["w"]), provenance
        hint = (suggestions or {}).get(key)
        if hint and (EMOJI_DIR / f"{hint}.png").is_file():
            code, prov = hint, "llm"
        if not code or code == last_code:
            continue
        if out and w["s"] - 0.05 < out[-1]["e"] + min_gap:
            continue
        f = EMOJI_DIR / f"{code}.png"
        if not f.is_file():
            continue
        s = max(0.0, w["s"] - 0.05)
        e = min(s + show, duration)
        if e - s < (EMOJI_IN_MS + EMOJI_OUT_MS) / 1000:
            continue
        out.append({"code": code, "s": round(s, 2), "e": round(e, 2), "file": str(f),
                    "provenance": prov, "keyword": w["w"],
                    "animation": {"in": "pop", "in_ms": EMOJI_IN_MS, "out": "fade", "out_ms": EMOJI_OUT_MS}})
        last_code = code
        if len(out) >= max_count:
            break
    return out


def plan_illustrations(words: list[dict], duration: float, max_count: int = 4, min_gap: float = 3.0) -> list[dict]:
    """Ilustrasi ringan buatan sendiri (garis aksen FFmpeg drawbox) hanya bila ada konteks semantik.

    Tanpa keyword relevan -> daftar kosong (batal aman). Tanpa aset pihak ketiga.
    """
    out: list[dict] = []
    for w in words:
        if not emoji_for(w["w"]):
            continue
        s = max(0.0, w["s"] - 0.05)
        if out and s < out[-1]["e"] + min_gap:
            continue
        e = min(s + 1.2, duration)
        if e - s < 0.5:
            continue
        out.append({"kind": "accent-line", "s": round(s, 2), "e": round(e, 2), "keyword": w["w"],
                    "provenance": "keyword", "asset": "generated:drawbox",
                    "animation": {"in": "fade", "in_ms": 200, "out": "fade", "out_ms": 200}})
        if len(out) >= max_count:
            break
    return out


def list_music() -> list[dict]:
    exts = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}
    return [{"name": f.stem, "file": str(f)} for f in sorted(MUSIC_DIR.iterdir()) if f.suffix.lower() in exts]
