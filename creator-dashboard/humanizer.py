"""Linter lokal untuk pola tulisan yang terdengar seperti AI, khusus bahasa Indonesia.

Hanya MENDETEKSI dan melapor; tidak menulis ulang teks, jadi fakta dan sitasi tidak bisa berubah.
Skor adalah heuristik editorial (100 = terdengar wajar), BUKAN prediksi hasil detektor AI mana pun.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

# ponytail: daftar klise ditulis tangan; tambah entri di sini bila menemukan pola baru, jangan buat file konfigurasi.
CLICHES = [
    (r"\bdi era (?:digital|modern|globalisasi|teknologi)(?: saat ini| ini)?", "pembuka 'di era digital'"),
    (r"\bdalam era (?:digital|modern|globalisasi)", "pembuka 'dalam era ...'"),
    (r"\btidak dapat dipungkiri(?: bahwa)?", "'tidak dapat dipungkiri'"),
    (r"\bperlu (?:dicatat|diingat|dipahami|dipertimbangkan) bahwa", "'perlu dicatat bahwa'"),
    (r"\bpenting untuk (?:dipahami|diingat|dicatat|diketahui) bahwa", "'penting untuk dipahami bahwa'"),
    (r"\bdapat disimpulkan bahwa", "'dapat disimpulkan bahwa'"),
    (r"\bsebagai kesimpulan\b", "'sebagai kesimpulan'"),
    (r"\bpada dasarnya\b", "'pada dasarnya'"),
    (r"\bmemainkan peran (?:yang )?(?:penting|krusial|kunci|vital)", "'memainkan peran penting'"),
    (r"\bseiring (?:dengan )?(?:berkembangnya|perkembangan|kemajuan)", "'seiring perkembangan'"),
    (r"\bdi tengah (?:pesatnya|derasnya|maraknya)", "'di tengah pesatnya'"),
    (r"\blanskap (?:digital|teknologi|keamanan|bisnis)", "'lanskap digital'"),
    (r"\bmenjadi hal yang (?:sangat )?(?:penting|krusial)", "'menjadi hal yang krusial'"),
    (r"\bhal ini (?:menunjukkan|menegaskan|membuktikan) bahwa", "'hal ini menunjukkan bahwa'"),
]
CONNECTORS = re.compile(
    r"^(?:selain itu|dengan demikian|oleh karena itu|oleh sebab itu|namun demikian|lebih lanjut|di samping itu|selanjutnya|sebagai tambahan)\b",
    re.I)
# "bukan sekadar X, melainkan Y" / "tidak hanya X, tetapi juga Y": satu kalimat, tanpa melewati tanda akhir kalimat.
NOT_ONLY = re.compile(
    r"\b(?:tidak|bukan)(?: hanya| sekadar| semata-mata| semata| cuma)\b[^.!?]{3,140}?\b(?:melainkan|tetapi juga|namun juga|tetapi|namun)\b",
    re.I)
MIN_SENTENCES = 8  # di bawah ini statistik kalimat tidak bermakna
WORD = re.compile(r"[\w\u00c0-\u00ff]+")


def _clean(text: str) -> str:
    text = re.sub(r"\*\*|__", "", text)
    return re.sub(r"\[\d+(?:\s*[,\u2013-]\s*\d+)*\]", "", text)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(WORD.findall(s)) >= 2]


def lint(text: str) -> dict:
    text = _clean(str(text or ""))
    sentences = _sentences(text)
    words = WORD.findall(text)
    findings: list[dict] = []

    def add(code: str, msg: str, penalty: int, examples: list[str]) -> int:
        findings.append({"code": code, "msg": msg, "examples": examples[:3]})
        return penalty

    penalty = 0
    hits = [(label, m.group(0)) for pattern, label in CLICHES for m in re.finditer(pattern, text, re.I)]
    for label in sorted({label for label, _ in hits}):
        penalty += add("klise", f"Frasa klise {label}; ganti dengan fakta atau langsung ke inti.", 10 if penalty < 40 else 0,
                       [seen for l, seen in hits if l == label])

    if len(sentences) >= MIN_SENTENCES:
        lengths = [len(WORD.findall(s)) for s in sentences]
        mean = statistics.mean(lengths)
        cv = statistics.pstdev(lengths) / mean if mean else 0
        if cv < 0.30:
            penalty += add("ritme", f"Panjang kalimat terlalu seragam (variasi {cv:.2f}); campur kalimat pendek dan panjang.", 15, [])
        starter, count = Counter(WORD.findall(s.lower())[0] for s in sentences).most_common(1)[0]
        if count >= 3 and count / len(sentences) >= 0.30:
            penalty += add("awalan", f"{count} dari {len(sentences)} kalimat dimulai dengan '{starter}'; variasikan pembuka kalimat.", 10, [])
        links = [s for s in sentences if CONNECTORS.match(s)]
        if len(links) >= 3 and len(links) / len(sentences) >= 0.20:
            penalty += add("penghubung", f"{len(links)} kalimat dibuka kata penghubung formal (selain itu, dengan demikian, ...); hapus yang tidak perlu.", 10,
                           [s[:60] for s in links])

    dashes = text.count("\u2014")
    if dashes >= 3 and dashes / max(len(words), 1) * 1000 > 5:
        penalty += add("tanda-pisah", f"Tanda pisah panjang (\u2014) muncul {dashes} kali; ganti dengan koma atau titik.", 8, [])
    pairs = [m.group(0) for m in NOT_ONLY.finditer(text)]
    if len(pairs) >= 3 and len(pairs) / max(len(words), 1) * 1000 >= 0.5:
        penalty += add("bukan-sekadar", f"Pola 'bukan sekadar X, melainkan Y' muncul {len(pairs)} kali; sebut Y langsung.", 12, [p[:80] for p in pairs])

    return {"score": max(0, 100 - penalty), "findings": findings,
            "metrics": {"words": len(words), "sentences": len(sentences)},
            "method": "heuristic_not_detector_prediction"}


def article_text(blocks: list[dict]) -> str:
    """Teks badan artikel (paragraf, daftar, kotak catatan) untuk dilint; tabel dan gambar dilewati."""
    parts = []
    for block in blocks:
        kind = block.get("type")
        if kind in ("p", "callout"):
            parts.append(str(block.get("text", "")))
        elif kind in ("bullets", "numbered"):
            parts += [str(item) + "." for item in block.get("items", [])]
    return "\n".join(parts)
