"""Pick an original animated illustration (motif) for any scene, from the user's own words.

Order of authority: explicit scene.motif (LLM or editor) > keyword score over subject,
on-screen text and narration (Indonesian + English) > deterministic rotation so
consecutive scenes never repeat. Motifs are decorative scenery, not evidence.
"""
from __future__ import annotations

import re

MOTIFS = ("elephant", "landmark", "birds", "map", "sunrise", "mountain", "city", "people", "tech", "nature",
          "water", "fire", "book", "idea", "globe", "money", "heart", "clock", "shield", "abstract")

KEYWORDS = {
    "elephant": "gajah elephant safari savana satwa hewan binatang animal wildlife kebun binatang",
    "landmark": "kabah ka'bah masjid mosque candi temple monumen monument gereja church museum istana palace menara tower landmark bangunan bersejarah",
    "birds": "burung bird terbang fly flock ababil sayap wings pesawat angkasa",
    "map": "peta map rute route perjalanan journey travel wisata lokasi negara jazirah wilayah navigasi petualangan destinasi",
    "sunrise": "fajar pagi sunrise terbit morning harapan awal dawn senja sunset cahaya sinar harapan",
    "mountain": "gunung mountain bukit hill pendakian hiking puncak tantangan rintangan",
    "city": "kota city urban gedung skyscraper metropolitan perkotaan jakarta kantor perusahaan",
    "people": "orang manusia people tim team komunitas community keluarga family masyarakat pengguna pelanggan audiens siswa murid teman warga",
    "tech": "teknologi technology komputer computer software aplikasi app data digital internet ai robot coding program siber cyber server startup gadget ponsel laptop algoritma otomatis",
    "nature": "alam nature hutan forest pohon tree tanaman plant kebun ladang pertanian lingkungan environment hijau petani jerami rumput bunga tumbuh benih",
    "water": "air water laut sea ocean samudra sungai river danau kapal ship hujan banjir pantai beach ombak berenang ikan",
    "fire": "api fire bakar kebakaran panas energi energy perang war ledakan membara semangat kompor bara marah",
    "book": "buku book belajar learn pendidikan education kitab quran naskah manuskrip membaca sekolah kuliah ilmu pengetahuan ayat surah doa tulisan riset penelitian materi kisah cerita",
    "idea": "ide idea inovasi innovation kreatif creative solusi solution tips trik strategi strategy pikiran gagasan insight rahasia cara metode kunci",
    "globe": "dunia world global internasional bumi earth planet universal seluruh semesta",
    "money": "uang money ekonomi economy bisnis business investasi invest saham harga biaya gaji keuangan finance profit untung harta kekayaan emas bank pajak menabung tabungan hemat",
    "heart": "cinta love hati heart kesehatan health sehat kasih empati peduli perasaan emosi jantung medis dokter donor darah sabar syukur bahagia",
    "clock": "waktu time jam clock menit detik deadline durasi tahun abad kronologi timeline masa kalender jadwal produktif kebiasaan rutin disiplin",
    "shield": "aman keamanan security lindung protect perlindungan benteng pertahanan defense digagalkan selamat kuat kekuatan kuasa pelindung privasi privacy risiko menjaga",
}
_PATTERNS = {motif: [re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)") for word in words.split()] for motif, words in KEYWORDS.items()}
ROTATION = ("sunrise", "globe", "idea", "city", "nature", "mountain", "clock", "water", "tech", "people")


def _score(text: str, motif: str) -> int:
    return sum(1 for pattern in _PATTERNS[motif] if pattern.search(text))


WEIGHTS = (("subject", 4), ("onScreenText", 3), ("visual", 2), ("narration", 1))


def scores(scene: dict) -> dict[str, int]:
    """Keyword score per motif for one scene (zero entries omitted)."""
    out = {}
    for motif in MOTIFS:
        if motif == "abstract":
            continue
        total = sum(weight * _score(str(scene.get(field) or "").casefold(), motif) for field, weight in WEIGHTS)
        if total:
            out[motif] = total
    return out


def pick(scene: dict) -> str:
    """Best single motif for one scene, or '' when nothing matches."""
    explicit = str(scene.get("motif") or "").strip()
    if explicit in MOTIFS:
        return explicit
    ranked = scores(scene)
    return max(ranked, key=ranked.get) if ranked else ""


def assign(scenes: list[dict]) -> list[str]:
    """Motif per scene: user words decide, repeats are penalised so a film shows variety.

    A motif already used costs 3 points per use; the previous scene's motif is never reused
    back-to-back. Scenes with no keyword hit rotate through a topic-independent list.
    """
    result: list[str] = []
    used: dict[str, int] = {}
    for index, scene in enumerate(scenes):
        previous = result[-1] if result else ""
        explicit = str(scene.get("motif") or "").strip()
        if explicit in MOTIFS:
            choice = explicit
        else:
            ranked = {m: s - 3 * used.get(m, 0) for m, s in scores(scene).items() if m != previous}
            positive = {m: s for m, s in ranked.items() if s > -3}
            if positive:
                choice = max(positive, key=positive.get)
            else:
                pool = [m for m in ROTATION if m != previous]
                pool.sort(key=lambda m: (used.get(m, 0), ROTATION.index(m)))
                choice = pool[index % min(3, len(pool))] if len(pool) > 3 and not used else pool[0]
        result.append(choice)
        used[choice] = used.get(choice, 0) + 1
    return result
