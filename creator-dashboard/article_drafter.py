"""Article Drafter: poin draft -> artikel panjang berstruktur (.md + .docx) + prompt gambar.

Pipeline bertahap (tiap tahap disimpan ke disk, jadi bisa dilanjutkan bila gagal di tengah):
  kerangka -> daftar rujukan -> tiap bagian (paralel) -> prompt gambar -> rakit .md/.docx
Gambar tidak dibuat di sini: tool menghasilkan prompt untuk Nano Banana / ChatGPT, hasilnya diunggah
kembali lalu dokumen dibangun ulang. Hanya stdlib; .docx ditulis langsung sebagai paket OOXML.
"""
from __future__ import annotations

import json
import os
import random
import re
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "output" / "articles"
LLM_URL = os.getenv("ARTICLE_LLM_BASE_URL", "http://localhost:20128/v1").rstrip("/")
LLM_MODEL = os.getenv("ARTICLE_LLM_MODEL", "ag/gemini-3.8-flash-high")
LLM_KEY = os.getenv("ARTICLE_LLM_API_KEY", "9router-local")
LLM_TIMEOUT = int(os.getenv("ARTICLE_LLM_TIMEOUT", "300"))
CONCURRENCY = max(1, min(6, int(os.getenv("ARTICLE_LLM_CONCURRENCY", "3"))))
RETRY_BASE_SECONDS = float(os.getenv("ARTICLE_LLM_RETRY_SECONDS", "3"))

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DOWNLOADS = {
    "article.md": "text/markdown; charset=utf-8",
    "article.docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image-prompts.md": "text/markdown; charset=utf-8",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FIELD = 20000
MAX_WORDS = 30000
MAX_IMAGES = 30
RANDOM_STYLE = "__random__"
ASPECTS = ("16:9", "1:1", "4:3", "9:16", "3:2")

STYLE_PRESETS = [
    "infografis bersih, flat, palet biru-ungu",
    "ilustrasi vektor minimalis, garis tipis, palet monokrom",
    "isometrik 3D bersih, warna pastel",
    "sketsa tangan gaya papan tulis putih, spidol berwarna",
    "papan tulis hitam dengan garis kapur putih",
    "poster retro vintage, tekstur kertas, palet hangat",
    "neon gelap futuristik, glow biru-magenta",
    "blueprint teknis, garis putih di latar biru tua",
    "papercut berlapis dengan bayangan lembut",
    "kartun datar ramah, warna cerah",
    "cat air lembut, palet pastel",
    "glassmorphism modern, gradasi ungu-biru",
    "foto editorial realistis, pencahayaan studio, komposisi bersih",
]

ARTICLE_TYPES = {
    "analisis": {
        "label": "Analisis mendalam / white paper (standar internasional)",
        "numbered": True,
        "abstract_heading": True,
        "structure": (
            "1. Pendahuluan (latar belakang, rumusan masalah, tujuan, ruang lingkup)\n"
            "2. Landasan konsep dan tinjauan pustaka\n"
            "3 sampai N-3. Pembahasan inti: satu bagian per tema; boleh memuat studi kasus, perbandingan, tabel\n"
            "N-2. Implikasi dan rekomendasi praktis\n"
            "N-1. Keterbatasan dan arah kajian lanjutan\n"
            "N. Kesimpulan"
        ),
    },
    "imrad": {
        "label": "Ilmiah IMRaD (untuk riset dan data milikmu)",
        "numbered": True,
        "abstract_heading": True,
        "structure": (
            "1. Pendahuluan (latar belakang, kesenjangan, tujuan, pertanyaan penelitian)\n"
            "2. Metode (HANYA metode yang diberikan pengguna; jangan mengarang prosedur)\n"
            "3. Hasil (HANYA data dari pengguna; jangan mengarang angka)\n"
            "4. Pembahasan (interpretasi, perbandingan dengan rujukan, implikasi)\n"
            "5. Keterbatasan\n"
            "6. Kesimpulan"
        ),
    },
    "laporan": {
        "label": "Laporan / studi kasus",
        "numbered": True,
        "abstract_heading": False,
        "structure": (
            "1. Ringkasan eksekutif\n2. Latar belakang\n3 sampai N-3. Temuan utama (satu bagian per tema)\n"
            "N-2. Analisis\nN-1. Rekomendasi dan langkah tindak lanjut\nN. Kesimpulan"
        ),
    },
    "populer": {
        "label": "Artikel populer / feature (blog, majalah)",
        "numbered": False,
        "abstract_heading": False,
        "structure": (
            "Pembuka yang menarik (hook), konteks singkat, isi utama dalam beberapa bagian bersubjudul, "
            "contoh atau kasus, langkah praktis, penutup dengan ajakan bertindak"
        ),
    },
    "tutorial": {
        "label": "Tutorial / panduan langkah demi langkah",
        "numbered": True,
        "abstract_heading": False,
        "structure": (
            "1. Gambaran umum dan hasil akhir\n2. Prasyarat\n3 sampai N-2. Langkah-langkah (satu bagian per tahap)\n"
            "N-1. Pemecahan masalah umum\nN. Ringkasan dan langkah berikutnya"
        ),
    },
}
DEFAULT_TYPE = "analisis"

LABELS = {
    "Indonesia": {
        "abstract": "Abstrak", "keywords": "Kata kunci", "toc": "Daftar Isi", "references": "Daftar Pustaka",
        "suggested": "Rujukan yang Disarankan (Belum Diverifikasi)",
        "suggested_note": "Daftar ini disarankan AI berdasarkan topik. Periksa keberadaan, penulis, tahun, dan isinya "
                          "sebelum dikutip. Jangan dipakai sebagai rujukan sebelum diverifikasi.",
    },
    "Inggris": {
        "abstract": "Abstract", "keywords": "Keywords", "toc": "Table of Contents", "references": "References",
        "suggested": "Suggested References (Unverified)",
        "suggested_note": "These references were suggested by AI from the topic. Verify that each exists, and check "
                          "its author, year, and content, before citing it.",
    },
}


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------- util

_XML_BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _s(value: object) -> str:
    return _XML_BAD.sub("", value).strip() if isinstance(value, str) else ""


def _str_list(value: object) -> list[str]:
    return [_s(item) for item in value if _s(item)] if isinstance(value, list) else []


def _clean_id(value: object) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(value or "").lower()).strip("-")[:40]


def count_words(blocks: list[dict]) -> int:
    texts: list[str] = []
    for block in blocks:
        kind = block.get("type")
        if kind in ("h2", "h3", "p"):
            texts.append(block.get("text", ""))
        elif kind in ("bullets", "numbered"):
            texts += block.get("items", [])
        elif kind == "callout":
            texts += [block.get("title", ""), block.get("text", "")]
        elif kind == "table":
            texts += block.get("header", []) + [c for row in block.get("rows", []) for c in row]
    return sum(len(re.findall(r"\w+", text)) for text in texts)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, default: object = None) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


# --------------------------------------------------------------------------- LLM

def _chat(messages: list[dict]) -> str:
    # stream=false wajib: 9Router default membalas SSE, bukan JSON
    body = json.dumps({"model": LLM_MODEL, "messages": messages, "temperature": 0.6, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        f"{LLM_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_KEY}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise LLMError(f"LLM tidak terjangkau di {LLM_URL}: {exc}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Respons LLM tidak dikenali: {str(data)[:200]}") from exc


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("tidak ada objek JSON")
    return json.loads(text[start:end + 1])


def _ask_json(system: str, user: str, normalizer):
    """Tanya LLM, validasi lewat normalizer. Galat jaringan: ulang dengan jeda. JSON buruk: minta perbaiki."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last = ""
    for attempt in range(3):
        try:
            content = _chat(messages)
        except LLMError as exc:
            last = str(exc)
            if attempt == 2:
                raise
            time.sleep(RETRY_BASE_SECONDS * (attempt + 1))
            continue
        try:
            return normalizer(_extract_json(content))
        except ValueError as exc:  # JSONDecodeError turunan ValueError
            last = str(exc)
            messages = messages + [
                {"role": "assistant", "content": content[:6000]},
                {"role": "user", "content": f"Keluaran tidak valid ({last}). Balas ulang HANYA dengan objek JSON yang benar."},
            ]
    raise LLMError(f"LLM tidak menghasilkan JSON valid setelah 3 percobaan: {last}")


# ------------------------------------------------------------- normalisasi keluaran

CITE_RE = re.compile(r"\[(\d+(?:\s*[,\u2013-]\s*\d+)*)\]")


def sanitize_citations(text: str, max_ref: int) -> str:
    """Penanda [n] hanya sah bila n ada di daftar rujukan; selain itu jadi [PERLU VERIFIKASI]."""
    def fix(match: re.Match) -> str:
        numbers = [int(n) for n in re.findall(r"\d+", match.group(1))]
        if any(n >= 1000 for n in numbers):  # tahun, bukan sitasi
            return match.group(0)
        return match.group(0) if all(1 <= n <= max_ref for n in numbers) else "[PERLU VERIFIKASI]"

    return CITE_RE.sub(fix, text)


def normalize_blocks(raw: object, image_ids: set[str], max_ref: int) -> list[dict]:
    """Batas kepercayaan: buang blok tak dikenal, h2 jadi h3, gambar hanya yang direncanakan, sitasi divalidasi."""
    cite = lambda t: sanitize_citations(t, max_ref)
    blocks: list[dict] = []
    used_images: set[str] = set()
    for block in raw if isinstance(raw, list) else []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind in ("h2", "h3"):
            if _s(block.get("text")):
                blocks.append({"type": "h3", "text": _s(block["text"])})
        elif kind == "p":
            if _s(block.get("text")):
                blocks.append({"type": "p", "text": cite(_s(block["text"]))})
        elif kind in ("bullets", "numbered"):
            items = [cite(i) for i in _str_list(block.get("items"))]
            if items:
                blocks.append({"type": kind, "items": items})
        elif kind == "callout":
            if _s(block.get("text")):
                blocks.append({"type": "callout", "title": _s(block.get("title")), "text": cite(_s(block["text"]))})
        elif kind == "table":
            header = _str_list(block.get("header"))
            rows = [[cite(_s(c)) for c in row] for row in (block.get("rows") or []) if isinstance(row, list)]
            if header and rows:
                rows = [(row + [""] * len(header))[:len(header)] for row in rows]
                blocks.append({"type": "table", "header": header, "rows": rows})
        elif kind == "image":
            image_id = _clean_id(block.get("id"))
            if image_id in image_ids and image_id not in used_images:
                used_images.add(image_id)
                blocks.append({"type": "image", "id": image_id, "caption": cite(_s(block.get("caption")))})
    return blocks


def normalize_outline(raw: object, inp: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("keluaran bukan objek JSON")
    sections: list[dict] = []
    for item in raw.get("sections") or []:
        if not isinstance(item, dict) or not _s(item.get("heading")):
            continue
        try:
            words = int(item.get("words") or 0)
        except (TypeError, ValueError, OverflowError):
            words = 0
        sections.append({
            "heading": re.sub(r"^\s*\d+(\.\d+)*[.)]?\s+", "", _s(item["heading"])),  # nomor ditambahkan sendiri
            "goal": _s(item.get("goal")),
            "subheadings": _str_list(item.get("subheadings"))[:6],
            "words": max(words, 80),
        })
        if len(sections) >= 40:
            break
    if not sections:
        raise ValueError("tidak ada bagian (sections) pada kerangka")
    total = sum(s["words"] for s in sections)
    for section in sections:  # skala ke target kata dari pengguna
        section["words"] = max(80, round(section["words"] * inp["words"] / total))
    images: list[dict] = []
    seen: set[str] = set()
    for item in raw.get("images") or []:
        if not isinstance(item, dict) or len(images) >= inp["image_count"]:
            continue
        image_id = _clean_id(item.get("id"))
        if not ID_RE.match(image_id) or image_id in seen:
            continue
        seen.add(image_id)
        try:
            section = int(item.get("section"))
        except (TypeError, ValueError, OverflowError):
            section = len(sections) - 1
        aspect = _s(item.get("aspect"))
        images.append({
            "id": image_id,
            "purpose": _s(item.get("purpose")),
            "aspect": aspect if aspect in ASPECTS else "16:9",
            "section": min(max(section, 0), len(sections) - 1),
        })
    assign_styles(images, inp["image_style"])
    return {
        "title": _s(raw.get("title")) or inp["title"] or "Artikel",
        "abstract": _s(raw.get("abstract")),
        "keywords": _str_list(raw.get("keywords"))[:8],
        "sections": sections,
        "images": images,
    }


def assign_styles(images: list[dict], choice: str) -> None:
    if choice == RANDOM_STYLE:
        pool = random.sample(STYLE_PRESETS, len(STYLE_PRESETS))
        for index, image in enumerate(images):
            image["style"] = pool[index % len(pool)]
    else:
        for image in images:
            image["style"] = choice


# ------------------------------------------------------------------------ prompts

BLOCK_SCHEMA = (
    '{"type":"h3","text":str} | {"type":"p","text":str} | {"type":"bullets","items":[str]} | '
    '{"type":"numbered","items":[str]} | {"type":"callout","title":str,"text":str} | '
    '{"type":"table","header":[str],"rows":[[str]]} | {"type":"image","id":"kebab-case","caption":str}'
)


def writing_rules(inp: dict) -> str:
    return f"""Aturan penulisan:
- Kamu penulis dan editor profesional. Bahasa: {inp['language']}. Nada: {inp['tone']}. Audiens: {inp['audience'] or 'umum'}.
- Fakta spesifik (angka, statistik, tanggal, nama orang atau lembaga, kutipan, hasil riset) HANYA dari poin dan sumber pengguna. Bila dibutuhkan tetapi tidak ada, hindari atau tulis [PERLU VERIFIKASI].
- Pengetahuan umum yang mapan (definisi, konsep dasar, prinsip) boleh dijelaskan tanpa sumber.
- Contoh ilustratif boleh, tetapi wajib berlabel 'Ilustrasi' dan jangan disajikan sebagai kejadian nyata.
- Kutip sumber dengan penanda [n] sesuai DAFTAR RUJUKAN yang diberikan. Jangan membuat nomor yang tidak ada.
- Kedalaman berasal dari penjelasan, alasan, perbandingan, contoh, dan implikasi. Jangan mengulang isi bagian lain dan jangan basa-basi.
- Teks polos. Satu-satunya format inline: **tebal**."""


OUTLINE_SYSTEM = """TAHAP: OUTLINE
Kamu editor kepala. Rancang kerangka artikel panjang. Balas HANYA dengan satu objek JSON valid:
{"title":str,"abstract":str,"keywords":[str],
 "sections":[{"heading":str,"goal":str,"subheadings":[str],"words":int}],
 "images":[{"id":"kebab-case","purpose":str,"aspect":"16:9|1:1|4:3|9:16|3:2","section":int}]}
Aturan:
- "heading" tanpa nomor. "goal" 1-2 kalimat: apa yang wajib dibahas bagian itu agar tidak tumpang tindih dengan bagian lain.
- "words" = target kata bagian itu; jumlah semuanya mendekati target total.
- "abstract": ringkasan mandiri (masalah, pendekatan, temuan atau isi utama, kesimpulan) tanpa sitasi. Panjang 120-250 kata untuk artikel panjang, 50-100 kata untuk artikel pendek.
- "keywords": 4-8 kata kunci.
- "section" pada images = indeks bagian (mulai 0) tempat gambar paling relevan. Sebar gambar merata. Jumlah gambar tepat sesuai permintaan.
- Isi hanya dari poin dan sumber pengguna; pengetahuan umum yang mapan boleh menjadi kerangka penjelasan."""

REFERENCES_SYSTEM = """TAHAP: REFERENSI
Kamu pustakawan. Balas HANYA dengan satu objek JSON valid: {"references":[str],"suggested":[str]}
Aturan:
- "references": ubah SUMBER dari pengguna menjadi entri daftar pustaka gaya IEEE (tanpa nomor di depan; nomor ditambahkan sistem). Satu entri per sumber berbeda, urutan sesuai kemunculan. Gunakan HANYA informasi yang ada di sumber. Bagian yang tidak diketahui (penulis, tahun, judul) jangan ditebak: tulis yang diketahui lalu tambahkan [lengkapi: penulis/tahun/judul]. Untuk URL: tambahkan "[Online]. Tersedia: URL. Diakses: TANGGAL." memakai tanggal akses yang diberikan.
- "suggested": hanya bila diminta. Daftar dokumen otoritatif yang kamu yakin ada (standar, laporan lembaga resmi, buku atau paper yang dikenal luas) dan relevan dengan topik. Maksimal 8. Jangan menulis DOI, nomor halaman, atau URL kecuali kamu yakin. Bila ragu tahun atau penerbit, tulis [periksa]. Jangan mengarang. Jika sumber pengguna kosong dan tidak diminta saran, kembalikan daftar kosong."""

SECTION_SYSTEM = f"""TAHAP: BAGIAN
Kamu menulis SATU bagian dari artikel panjang. Balas HANYA dengan satu objek JSON valid: {{"blocks":[...]}}
Skema blok: {BLOCK_SCHEMA}
Aturan blok:
- JANGAN menulis judul bagian utama (sudah ditambahkan sistem); gunakan blok h3 untuk subjudul.
- Ikuti subjudul yang diberikan (jika ada) sebagai h3, berurutan.
- Variasikan bentuk: paragraf padat, daftar, tabel perbandingan, kotak catatan (callout) bila membantu.
- Blok image hanya untuk id yang diminta; letakkan di tempat paling relevan di dalam bagian.
- Target panjang diberikan dalam kata; capai mendekati target dengan isi bermakna."""

EXPAND_SYSTEM = f"""TAHAP: PERLUAS
Bagian artikel berikut masih lebih pendek dari target. Tulis blok TAMBAHAN (tanpa mengulang apa yang sudah ada) yang menambah kedalaman: alasan, perbandingan, contoh berlabel Ilustrasi, kesalahan umum, daftar periksa, atau implikasi.
Balas HANYA dengan satu objek JSON valid: {{"blocks":[...]}} dengan skema blok: {BLOCK_SCHEMA}. Jangan menyertakan blok image."""

IMAGE_SYSTEM = """TAHAP: GAMBAR
Kamu art director. Untuk setiap gambar yang diminta, tulis prompt untuk generator gambar (Nano Banana / ChatGPT).
Balas HANYA dengan satu objek JSON valid: {"images":[{"id":str,"alt":str,"prompt":str}]}
Aturan:
- "prompt": bahasa Inggris, mandiri (bisa langsung ditempel), sebut subjek, komposisi, gaya visual (ikuti GAYA yang diberikan), palet warna, rasio, dan teks yang tampil di dalam gambar (dalam bahasa yang diminta, dieja persis, singkat). Tanpa watermark dan tanpa logo merek.
- "alt": teks alternatif 1 kalimat dalam bahasa artikel.
- Satu entri per id yang diminta, id persis sama."""


def build_outline_prompt(inp: dict) -> str:
    kind = ARTICLE_TYPES[inp["article_type"]]
    suggested = max(4, min(36, round(inp["words"] / 900)))
    parts = [
        writing_rules(inp), "",
        f"Judul kerja: {inp['title'] or '(usulkan judul sendiri)'}",
        f"Jenis artikel: {kind['label']}",
        f"Struktur WAJIB diikuti (N = jumlah bagian):\n{kind['structure']}",
        f"Target total isi: {inp['words']} kata. Usulkan sekitar {suggested} bagian.",
        f"Jumlah gambar: {inp['image_count']}",
        "",
        "POIN DRAFT DARI PENGGUNA:", inp["points"],
    ]
    if inp["sources"]:
        parts += ["", "SUMBER / CATATAN:", inp["sources"]]
    if inp["image_requests"]:
        parts += ["", "PERMINTAAN GAMBAR (satu per baris; wujudkan sebagai gambar):", inp["image_requests"]]
    return "\n".join(parts)


def build_section_prompt(inp: dict, outline: dict, refs: dict, index: int) -> str:
    section = outline["sections"][index]
    images = [im for im in outline["images"] if im["section"] == index]
    parts = [
        writing_rules(inp), "",
        f"Judul artikel: {outline['title']}",
        "KERANGKA ARTIKEL:",
        *[f"{i + 1}. {s['heading']} - {s['goal']}" for i, s in enumerate(outline["sections"])],
        "",
        f"BAGIAN NOMOR: {index + 1}",
        f"Judul bagian: {section['heading']}",
        f"Tujuan bagian: {section['goal']}",
        f"Subjudul (h3) berurutan: {'; '.join(section['subheadings']) or '(bebas, sesuaikan)'}",
        f"Target panjang: sekitar {section['words']} kata",
        "GAMBAR UNTUK BAGIAN INI (sisipkan blok image dengan id persis): "
        + (", ".join(f"{im['id']} ({im['purpose']})" for im in images) or "tidak ada"),
        "",
        "DAFTAR RUJUKAN (kutip dengan [n]):",
        *([f"[{i + 1}] {r}" for i, r in enumerate(refs["references"])] or ["(kosong; jangan membuat sitasi)"]),
        "",
        "POIN DRAFT DARI PENGGUNA:", inp["points"],
    ]
    if inp["sources"]:
        parts += ["", "SUMBER / CATATAN:", inp["sources"]]
    return "\n".join(parts)


# ---------------------------------------------------------------------- tahapan

def make_outline(inp: dict) -> dict:
    return _ask_json(OUTLINE_SYSTEM, build_outline_prompt(inp), lambda raw: normalize_outline(raw, inp))


MONTHS = {
    "Indonesia": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
                  "Oktober", "November", "Desember"],
    "Inggris": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                "October", "November", "December"],
}


def access_date(language: str) -> str:
    now = time.localtime()
    return f"{now.tm_mday} {MONTHS.get(language, MONTHS['Indonesia'])[now.tm_mon - 1]} {now.tm_year}"


def make_references(inp: dict) -> dict:
    if not inp["sources"] and not inp["suggest_refs"]:
        return {"references": [], "suggested": []}

    def norm(raw: object) -> dict:
        if not isinstance(raw, dict):
            raise ValueError("keluaran bukan objek JSON")
        refs = _str_list(raw.get("references"))[:200] if inp["sources"] else []
        suggested = _str_list(raw.get("suggested"))[:8] if inp["suggest_refs"] else []
        return {"references": refs, "suggested": suggested}

    user = "\n".join([
        f"Bahasa artikel: {inp['language']}",
        f"Topik: {inp['title'] or inp['points'][:200]}",
        f"Tanggal akses: {access_date(inp['language'])}",
        f"Minta saran rujukan tambahan: {'ya' if inp['suggest_refs'] else 'tidak'}",
        "", "SUMBER DARI PENGGUNA:", inp["sources"] or "(kosong)",
        "", "POIN DRAFT (hanya untuk konteks topik):", inp["points"][:3000],
    ])
    return _ask_json(REFERENCES_SYSTEM, user, norm)


def write_section(inp: dict, outline: dict, refs: dict, index: int) -> dict:
    section = outline["sections"][index]
    ids = {im["id"] for im in outline["images"] if im["section"] == index}
    max_ref = len(refs["references"])

    def norm(raw: object) -> list[dict]:
        if not isinstance(raw, dict):
            raise ValueError("keluaran bukan objek JSON")
        blocks = normalize_blocks(raw.get("blocks"), ids, max_ref)
        if not blocks:
            raise ValueError("bagian kosong")
        return blocks

    blocks = _ask_json(SECTION_SYSTEM, build_section_prompt(inp, outline, refs, index), norm)
    expanded = False
    words = count_words(blocks)
    if section["words"] >= 300 and words < 0.7 * section["words"]:
        existing = "\n".join(
            b.get("text", "") or " ".join(b.get("items", [])) for b in blocks if b["type"] in ("p", "h3", "bullets", "numbered")
        )
        user = (
            f"{writing_rules(inp)}\n\nJudul bagian: {section['heading']}\nTujuan: {section['goal']}\n"
            f"Sudah ada ± {words} kata, target {section['words']}. Tambahkan ± {section['words'] - words} kata.\n\n"
            f"TEKS YANG SUDAH ADA:\n{existing[:12000]}\n\n"
            "DAFTAR RUJUKAN:\n" + ("\n".join(f"[{i + 1}] {r}" for i, r in enumerate(refs["references"])) or "(kosong)")
        )
        try:
            blocks = blocks + _ask_json(EXPAND_SYSTEM, user, norm)
            expanded = True
        except LLMError:
            pass  # bagian asli tetap sah; lebih pendek dari target lebih baik daripada gagal
    return {"blocks": blocks, "words": count_words(blocks), "expanded": expanded}


def make_image_prompts(inp: dict, outline: dict) -> list[dict]:
    images = outline["images"]
    result: list[dict] = []
    for start in range(0, len(images), 6):
        chunk = images[start:start + 6]
        want = {im["id"] for im in chunk}

        def norm(raw: object, want: set[str] = want) -> dict:
            if not isinstance(raw, dict):
                raise ValueError("keluaran bukan objek JSON")
            found = {}
            for item in raw.get("images") or []:
                if isinstance(item, dict) and _clean_id(item.get("id")) in want and _s(item.get("prompt")):
                    found[_clean_id(item["id"])] = {"alt": _s(item.get("alt")), "prompt": _s(item["prompt"])}
            missing = sorted(want - found.keys())
            if missing:
                raise ValueError(f"prompt belum ada untuk: {', '.join(missing)}")
            return found

        user = "\n".join([
            f"Bahasa artikel: {inp['language']}",
            f"Bahasa teks di dalam gambar: {inp['image_text_language']}",
            f"Judul artikel: {outline['title']}", "",
            "GAMBAR YANG DIMINTA:",
            *[
                f"- {im['id']}: fungsi={im['purpose'] or '-'}; rasio={im['aspect']}; GAYA={im['style']}; "
                f"bagian artikel='{outline['sections'][im['section']]['heading']}'"
                for im in chunk
            ],
        ])
        found = _ask_json(IMAGE_SYSTEM, user, norm)
        for im in chunk:
            result.append({**im, "alt": found[im["id"]]["alt"] or im["id"], "prompt": found[im["id"]]["prompt"]})
    return result


def assemble(slug: str) -> dict:
    directory = _dir(slug)
    inp = _read_json(directory / "input.json")
    outline = _read_json(directory / "outline.json")
    refs = _read_json(directory / "references.json", {"references": [], "suggested": []})
    images = _read_json(directory / "prompts.json", [])
    kind = ARTICLE_TYPES[inp["article_type"]]
    by_id = {im["id"]: im for im in images}
    placed: set[str] = set()
    blocks: list[dict] = []
    for index, section in enumerate(outline["sections"]):
        data = _read_json(directory / "sections" / f"{index:02d}.json")
        body = []
        for block in data["blocks"]:
            if block["type"] == "image":
                if block["id"] not in by_id or block["id"] in placed:
                    continue
                placed.add(block["id"])
            body.append(block)
        for image in images:  # gambar yang terlewat penulis bagian: taruh di akhir bagiannya
            if image["section"] == index and image["id"] not in placed:
                placed.add(image["id"])
                body.append({"type": "image", "id": image["id"], "caption": image["alt"]})
        blocks.append({"type": "h2", "text": section["heading"]})
        blocks += body
    article = {
        "title": outline["title"],
        "lang": inp["language"] if inp["language"] in LABELS else "Indonesia",
        "type": inp["article_type"],
        "summary": outline["abstract"],
        "keywords": outline["keywords"],
        "numbered": kind["numbered"],
        "abstract_heading": kind["abstract_heading"],
        "toc": kind["numbered"] and inp["words"] >= 3000,
        "blocks": blocks,
        "images": images,
        "references": refs["references"],
        "suggested_references": refs["suggested"],
        "generated": time.strftime("%Y-%m-%d"),
    }
    _write_json(directory / "article.json", article)
    return article


# ------------------------------------------------------------------------- input

def clean_input(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("input harus objek JSON")

    def text(key: str, default: str = "") -> str:
        value = _s(raw.get(key)) or default
        if len(value) > MAX_FIELD:
            raise ValueError(f"Field '{key}' terlalu panjang (maks {MAX_FIELD} karakter)")
        return value

    def number(key: str, default: int, low: int, high: int) -> int:
        try:
            value = int(raw.get(key) if raw.get(key) not in (None, "") else default)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"Field '{key}' harus berupa angka") from None
        return min(max(value, low), high)

    article_type = text("article_type", DEFAULT_TYPE)
    language = text("language", "Indonesia")
    style = text("image_style", STYLE_PRESETS[0])
    inp = {
        "title": text("title"),
        "audience": text("audience"),
        "language": language if language in LABELS else "Indonesia",
        "tone": text("tone", "semi-formal"),
        "article_type": article_type if article_type in ARTICLE_TYPES else DEFAULT_TYPE,
        "words": number("words", 1200, 200, MAX_WORDS),
        "points": text("points"),
        "sources": text("sources"),
        "suggest_refs": str(raw.get("suggest_refs", "")).lower() in ("1", "true", "on", "yes"),
        "image_count": number("image_count", 0, 0, MAX_IMAGES),
        "image_requests": text("image_requests"),
        "image_style": style,
        "image_text_language": text("image_text_language", "Indonesia"),
    }
    if not inp["points"]:
        raise ValueError("Poin draft wajib diisi")
    return inp


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-") or "artikel"
    return f"{base}-{time.strftime('%m%d-%H%M%S')}-{uuid.uuid4().hex[:2]}"


def create(raw_input: object) -> str:
    inp = clean_input(raw_input)
    slug = slugify(inp["title"] or inp["points"][:40])
    directory = ARTICLES_DIR / slug
    (directory / "images").mkdir(parents=True, exist_ok=True)
    _write_json(directory / "input.json", inp)
    return slug


# ---------------------------------------------------------------------- pipeline

def run_pipeline(slug: str, report=None) -> dict:
    """Jalankan/lanjutkan pipeline. Tahap yang sudah punya berkas di disk dilewati."""
    report = report or (lambda step, done, total, message: None)
    directory = _dir(slug)
    inp = _read_json(directory / "input.json")
    if inp is None:
        raise FileNotFoundError(slug)

    outline = _read_json(directory / "outline.json")
    if outline is None:
        report("outline", 0, 1, "Menyusun kerangka artikel")
        outline = make_outline(inp)
        _write_json(directory / "outline.json", outline)
    count = len(outline["sections"])
    total = count + 4  # kerangka + rujukan + bagian + gambar + rakit
    done = 1

    refs = _read_json(directory / "references.json")
    if refs is None:
        report("references", done, total, "Menyusun daftar pustaka")
        refs = make_references(inp)
        _write_json(directory / "references.json", refs)
    done += 1

    pending = [i for i in range(count) if not (directory / "sections" / f"{i:02d}.json").is_file()]
    done += count - len(pending)
    failures: list[str] = []
    if pending:
        report("sections", done, total, f"Menulis {len(pending)} bagian ({CONCURRENCY} paralel)")

        def job(index: int) -> int:
            data = write_section(inp, outline, refs, index)
            _write_json(directory / "sections" / f"{index:02d}.json", data)
            return index

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(job, i): i for i in pending}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    future.result()
                    done += 1
                    report("sections", done, total, f"Bagian selesai: {outline['sections'][index]['heading']}")
                except (LLMError, ValueError) as exc:
                    failures.append(f"bagian {index + 1} ({outline['sections'][index]['heading']}): {exc}")
    if failures:
        raise LLMError("Gagal: " + "; ".join(failures[:3]) + ". Hasil yang sudah jadi tersimpan; klik Lanjutkan.")

    if _read_json(directory / "prompts.json") is None:
        report("images", done, total, "Menulis prompt gambar")
        _write_json(directory / "prompts.json", make_image_prompts(inp, outline))
    done += 1

    report("assemble", done, total, "Merakit artikel")
    assemble(slug)
    build_outputs(slug)
    report("done", total, total, "Selesai")
    return get_article(slug)


def generate(raw_input: object) -> dict:
    """Sinkron (untuk tes/CLI). Server memakai start_job."""
    slug = create(raw_input)
    return run_pipeline(slug)


# --------------------------------------------------------------------------- job

JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _spawn(slug: str) -> dict:
    with _jobs_lock:
        for job in JOBS.values():
            if job["slug"] == slug and job["status"] == "running":
                return dict(job)
        now = time.time()
        for key in [k for k, j in JOBS.items() if j["status"] != "running" and now - j["updated"] > 3600]:
            del JOBS[key]
        job = {"id": uuid.uuid4().hex[:12], "slug": slug, "status": "running", "step": "start",
               "done": 0, "total": 1, "message": "Memulai", "error": "", "updated": now}
        JOBS[job["id"]] = job

    def report(step: str, done: int, total: int, message: str) -> None:
        with _jobs_lock:
            job.update(step=step, done=done, total=total, message=message, updated=time.time())

    def run() -> None:
        try:
            run_pipeline(slug, report)
            outcome = {"status": "done", "message": "Selesai"}
        except Exception as exc:  # noqa: BLE001 - thread latar belakang: lapor ke UI, jangan mati diam-diam
            outcome = {"status": "error", "error": str(exc) or type(exc).__name__}
        with _jobs_lock:
            job.update(outcome, updated=time.time())

    threading.Thread(target=run, daemon=True).start()
    return dict(job)


def start_job(raw_input: object) -> dict:
    return _spawn(create(raw_input))


def resume_job(slug: str) -> dict:
    _dir(slug)
    return _spawn(slug)


def job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = JOBS.get(job_id)
        if job is None:
            raise FileNotFoundError(job_id)
        return dict(job)


def options() -> dict:
    return {
        "types": [{"key": key, "label": value["label"]} for key, value in ARTICLE_TYPES.items()],
        "defaultType": DEFAULT_TYPE,
        "styles": STYLE_PRESETS,
        "randomStyle": RANDOM_STYLE,
        "limits": {"maxWords": MAX_WORDS, "maxImages": MAX_IMAGES},
    }


# ------------------------------------------------------------------ file helpers

def _dir(slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise ValueError("slug tidak valid")
    directory = (ARTICLES_DIR / slug).resolve()
    if directory.parent != ARTICLES_DIR.resolve() or not directory.is_dir():
        raise FileNotFoundError(slug)
    return directory


def find_image(directory: Path, image_id: str) -> Path | None:
    for ext in ("png", "jpg"):
        candidate = directory / "images" / f"{image_id}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def image_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:3] == b"\xff\xd8\xff":
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
                return width, height
            pos += 2 + length
    return None


def get_article(slug: str) -> dict:
    directory = _dir(slug)
    inp = _read_json(directory / "input.json", {})
    article = _read_json(directory / "article.json")
    if article is None:  # belum selesai (atau gagal di tengah)
        outline = _read_json(directory / "outline.json")
        total = len(outline["sections"]) if outline else 0
        done = len(list((directory / "sections").glob("*.json"))) if (directory / "sections").is_dir() else 0
        return {"slug": slug, "complete": False, "title": (outline or {}).get("title") or inp.get("title") or slug,
                "summary": "", "images": [], "markdown": "", "files": [], "path": str(directory),
                "sectionsDone": done, "sectionsTotal": total, "wordCount": 0, "referencesCount": 0}
    images = [{**image, "hasFile": find_image(directory, image["id"]) is not None} for image in article["images"]]
    return {
        "slug": slug,
        "complete": True,
        "title": article["title"],
        "summary": article["summary"],
        "images": images,
        "markdown": (directory / "article.md").read_text(encoding="utf-8"),
        "files": [name for name in DOWNLOADS if (directory / name).is_file()],
        "path": str(directory),
        "wordCount": count_words(article["blocks"]),
        "referencesCount": len(article.get("references", [])),
    }


def list_articles() -> list[dict]:
    if not ARTICLES_DIR.is_dir():
        return []
    running = {}
    with _jobs_lock:
        for job in JOBS.values():
            if job["status"] == "running":
                running[job["slug"]] = job["id"]
    items = []
    for directory in sorted(ARTICLES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not (directory.is_dir() and (directory / "input.json").is_file()):
            continue
        try:
            article = _read_json(directory / "article.json")
            inp = _read_json(directory / "input.json", {})
            outline = _read_json(directory / "outline.json") or {}
        except ValueError:
            continue
        title = (article or {}).get("title") or outline.get("title") or inp.get("title") or directory.name
        items.append({"slug": directory.name, "title": title, "complete": article is not None,
                      "job": running.get(directory.name)})
    return items


def read_file(slug: str, name: str) -> tuple[bytes, str]:
    if name not in DOWNLOADS:
        raise FileNotFoundError(name)
    path = _dir(slug) / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path.read_bytes(), DOWNLOADS[name]


def save_image(slug: str, image_id: str, data: bytes) -> dict:
    directory = _dir(slug)
    article = _read_json(directory / "article.json")
    if article is None:
        raise ValueError("Artikel belum selesai dibuat")
    if image_id not in {image["id"] for image in article["images"]}:
        raise ValueError("id gambar tidak ada di artikel ini")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Gambar lebih dari 10 MB")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = "png"
    elif data[:3] == b"\xff\xd8\xff":
        ext = "jpg"
    else:
        raise ValueError("Hanya PNG atau JPG yang diterima")
    if image_size(data) is None:
        raise ValueError("Ukuran gambar tidak terbaca; file mungkin rusak")
    for other in ("png", "jpg"):
        (directory / "images" / f"{image_id}.{other}").unlink(missing_ok=True)
    (directory / "images" / f"{image_id}.{ext}").write_bytes(data)
    build_outputs(slug)
    return get_article(slug)


def build_outputs(slug: str) -> dict:
    directory = _dir(slug)
    article = _read_json(directory / "article.json")
    if article is None:
        raise FileNotFoundError("article.json")
    (directory / "article.md").write_text(to_markdown(article, directory), encoding="utf-8")
    (directory / "image-prompts.md").write_text(to_prompts_markdown(article), encoding="utf-8")
    to_docx(article, directory, directory / "article.docx")
    return get_article(slug)


# ----------------------------------------------------------- penomoran, DOC, MD

def _labels(article: dict) -> dict:
    return LABELS.get(article.get("lang"), LABELS["Indonesia"])


def numbered_blocks(article: dict) -> list[dict]:
    """Beri nomor 1., 1.1 pada judul bila jenis artikel menuntutnya (default bagi artikel lama: tidak)."""
    if not article.get("numbered"):
        return article["blocks"]
    out, h2, h3 = [], 0, 0
    for block in article["blocks"]:
        if block["type"] == "h2":
            h2, h3 = h2 + 1, 0
            out.append({**block, "text": f"{h2}. {block['text']}"})
        elif block["type"] == "h3":
            h3 += 1
            out.append({**block, "text": f"{h2}.{h3} {block['text']}" if h2 else f"{h3}. {block['text']}"})
        else:
            out.append(block)
    return out


def toc_entries(blocks: list[dict]) -> list[tuple[int, str]]:
    return [(1 if b["type"] == "h2" else 2, b["text"]) for b in blocks if b["type"] in ("h2", "h3")]


def to_markdown(article: dict, directory: Path | None = None) -> str:
    labels = _labels(article)
    images = {image["id"]: image for image in article["images"]}
    blocks = numbered_blocks(article)
    lines = [f"# {article['title']}", ""]
    summary, keywords = article.get("summary", ""), article.get("keywords", [])
    if summary and article.get("abstract_heading"):
        lines += [f"## {labels['abstract']}", "", summary, ""]
        if keywords:
            lines += [f"**{labels['keywords']}:** " + "; ".join(keywords), ""]
    elif summary:
        lines += [f"> {summary}", ""]
    if article.get("toc"):
        lines += [f"## {labels['toc']}", ""]
        lines += [("  " * (level - 1)) + f"- {text}" for level, text in toc_entries(blocks)] + [""]
    for block in blocks:
        kind = block["type"]
        if kind == "h2":
            lines += [f"## {block['text']}", ""]
        elif kind == "h3":
            lines += [f"### {block['text']}", ""]
        elif kind == "p":
            lines += [block["text"], ""]
        elif kind == "bullets":
            lines += [f"- {item}" for item in block["items"]] + [""]
        elif kind == "numbered":
            lines += [f"{i}. {item}" for i, item in enumerate(block["items"], 1)] + [""]
        elif kind == "callout":
            title = f"**{block['title']}** " if block["title"] else ""
            lines += [f"> {title}{block['text']}", ""]
        elif kind == "table":
            cell = lambda t: t.replace("|", "\\|").replace("\n", " ")
            lines.append("| " + " | ".join(cell(h) for h in block["header"]) + " |")
            lines.append("|" + "---|" * len(block["header"]))
            lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in block["rows"]] + [""]
        elif kind == "image":
            image = images[block["id"]]
            found = find_image(directory, image["id"]) if directory else None
            name = found.name if found else f"{image['id']}.png"
            lines.append(f"![{image['alt']}](images/{name})")
            if block["caption"]:
                lines.append(f"*{block['caption']}*")
            lines.append("")
    if article.get("references"):
        lines += [f"## {labels['references']}", ""]
        lines += [f"[{i}] {ref}  " for i, ref in enumerate(article["references"], 1)] + [""]
    if article.get("suggested_references"):
        lines += [f"## {labels['suggested']}", "", f"> {labels['suggested_note']}", ""]
        lines += [f"- {ref}" for ref in article["suggested_references"]] + [""]
    return "\n".join(lines).rstrip() + "\n"


def to_prompts_markdown(article: dict) -> str:
    lines = [
        f"# Prompt gambar: {article['title']}",
        "",
        "Tempel prompt ke Nano Banana atau ChatGPT. Simpan hasilnya, lalu unggah di halaman artikel "
        "(atau taruh sebagai `images/<id>.png` / `.jpg`) dan klik Bangun ulang.",
        "",
    ]
    if not article["images"]:
        lines.append("Artikel ini tidak meminta gambar.")
    for image in article["images"]:
        lines += [
            f"## {image['id']}",
            f"- Fungsi: {image['purpose'] or '-'}",
            f"- Rasio: {image['aspect']}",
            f"- Gaya: {image.get('style', '-')}",
            f"- Alt text: {image['alt']}",
            "",
            "```text",
            image["prompt"],
            "```",
            "",
        ]
    return "\n".join(lines)


# ------------------------------------------------------------------------- DOCX

_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _run(text: str, bold: bool = False, italic: bool = False, color: str = "") -> str:
    props = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + (f'<w:color w:val="{color}"/>' if color else "")
    return f'<w:r>{f"<w:rPr>{props}</w:rPr>" if props else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _runs(text: str, bold: bool = False, italic: bool = False, color: str = "") -> str:
    # split dengan grup: indeks ganjil = teks di dalam **...**
    return "".join(
        _run(part, bold or index % 2 == 1, italic, color)
        for index, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)) if part
    )


def _p(runs: str = "", style: str = "", jc: str = "", ind: tuple[int, int] | None = None) -> str:
    props = (
        (f'<w:pStyle w:val="{style}"/>' if style else "")
        + (f'<w:ind w:left="{ind[0]}" w:hanging="{ind[1]}"/>' if ind else "")
        + (f'<w:jc w:val="{jc}"/>' if jc else "")
    )
    return f'<w:p>{f"<w:pPr>{props}</w:pPr>" if props else ""}{runs}</w:p>'


def _table(header: list[str], rows: list[list[str]]) -> str:
    def cell(text: str, head: bool) -> str:
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8EAFE"/>' if head else ""
        return f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/>{shade}</w:tcPr>{_p(_runs(text, bold=head))}</w:tc>'

    def row(cells: list[str], head: bool) -> str:
        return "<w:tr>" + "".join(cell(c, head) for c in cells) + "</w:tr>"

    borders = "".join(
        f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="9AA0C0"/>'
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    grid = "".join('<w:gridCol w:w="2000"/>' for _ in header)
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{borders}</w:tblBorders></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{row(header, True)}{''.join(row(r, False) for r in rows)}</w:tbl>{_p()}"
    )


def _drawing(rid: str, number: int, alt: str, width_px: int, height_px: int) -> str:
    cx = 5486400  # 6 inci
    cy = int(cx * height_px / width_px)
    if cy > 7315200:  # maks 8 inci tinggi
        cx, cy = int(cx * 7315200 / cy), 7315200
    alt_attr = escape(alt, {'"': "&quot;"})
    return (
        f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{number}" name="Gambar {number}" descr="{alt_attr}"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{number}" name="gambar-{number}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
    )


def _style(style_id: str, name: str, ppr: str = "", rpr: str = "") -> str:
    based = '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
    ppr_xml = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    rpr_xml = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (
        f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/>'
        f"{based}<w:qFormat/>{ppr_xml}{rpr_xml}</w:style>"
    )


def _styles_xml() -> str:
    heading = lambda n, size, level: _style(
        f"Heading{n}", f"heading {n}",
        f'<w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="{level}"/>',
        f'<w:b/><w:color w:val="2B2F6B"/><w:sz w:val="{size}"/>',
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}>'
        '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
        '<w:sz w:val="22"/><w:lang w:val="id-ID"/></w:rPr></w:rPrDefault>'
        '<w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
        + _style("Title", "Title", '<w:spacing w:after="160"/>', '<w:b/><w:color w:val="2B2F6B"/><w:sz w:val="48"/>')
        + heading(1, 32, 0) + heading(2, 26, 1)
        + _style("Callout", "Callout",
                 '<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="7C8CFF"/></w:pBdr>'
                 '<w:shd w:val="clear" w:color="auto" w:fill="F0F2FF"/><w:spacing w:before="120" w:after="200"/>'
                 '<w:ind w:left="240" w:right="240"/>')
        + _style("Caption", "caption", '<w:spacing w:after="240"/><w:jc w:val="center"/>', '<w:i/><w:color w:val="5A607F"/><w:sz w:val="18"/>')
        + "</w:styles>"
    )


_FOOTER = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {_W}><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
    "</w:p></w:ftr>"
)
_PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def to_docx(article: dict, directory: Path, target: Path) -> None:
    labels = _labels(article)
    images = {image["id"]: image for image in article["images"]}
    blocks = numbered_blocks(article)
    media: list[tuple[str, bytes]] = []  # (nama file di paket, isi)
    body: list[str] = [_p(_runs(article["title"]), "Title")]
    summary, keywords = article.get("summary", ""), article.get("keywords", [])
    if summary and article.get("abstract_heading"):
        body += [_p(_runs(labels["abstract"]), "Heading1"), _p(_runs(summary))]
        if keywords:
            body.append(_p(_run(f"{labels['keywords']}: ", bold=True) + _run("; ".join(keywords), italic=True)))
    elif summary:
        body.append(_p(_runs(summary, italic=True, color="5A607F")))
    if article.get("toc"):
        body.append(_p(_runs(labels["toc"]), "Heading1"))
        for level, text in toc_entries(blocks):
            body.append(_p(_runs(text, bold=level == 1), ind=(0 if level == 1 else 360, 0)))
        body.append(_PAGE_BREAK)
    for block in blocks:
        kind = block["type"]
        if kind == "h2":
            body.append(_p(_runs(block["text"]), "Heading1"))
        elif kind == "h3":
            body.append(_p(_runs(block["text"]), "Heading2"))
        elif kind == "p":
            body.append(_p(_runs(block["text"])))
        elif kind in ("bullets", "numbered"):
            for index, item in enumerate(block["items"], 1):
                marker = "•" if kind == "bullets" else f"{index}."
                body.append(_p(_run(f"{marker}\u00a0\u00a0") + _runs(item), ind=(560, 280)))
        elif kind == "callout":
            title = _run(block["title"] + " ", bold=True) if block["title"] else ""
            body.append(_p(title + _runs(block["text"]), "Callout"))
        elif kind == "table":
            body.append(_table(block["header"], block["rows"]))
        elif kind == "image":
            image = images[block["id"]]
            found = find_image(directory, image["id"])
            data = found.read_bytes() if found else b""
            size = image_size(data) if data else None
            if size:
                name = f"image{len(media) + 1}{found.suffix}"
                media.append((name, data))
                rid = f"rId{len(media) + 10}"
                body.append(_p(_drawing(rid, len(media), image["alt"], *size), jc="center"))
            else:
                note = f"[GAMBAR: {image['id']}] {image['purpose']} (prompt ada di image-prompts.md)"
                body.append(_p(_run(note, italic=True, color="8A6D00"), "Callout"))
            if block["caption"]:
                body.append(_p(_runs(block["caption"]), "Caption"))
    if article.get("references"):
        body.append(_p(_runs(labels["references"]), "Heading1"))
        body += [_p(_runs(f"[{i}] {ref}"), ind=(560, 560)) for i, ref in enumerate(article["references"], 1)]
    if article.get("suggested_references"):
        body.append(_p(_runs(labels["suggested"]), "Heading1"))
        body.append(_p(_runs(labels["suggested_note"], italic=True, color="8A6D00"), "Callout"))
        body += [_p(_run("•\u00a0\u00a0") + _runs(ref), ind=(560, 280)) for ref in article["suggested_references"]]
    section = (
        '<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_NS}><w:body>{"".join(body)}{section}</w:body></w:document>'
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        + "".join(
            f'<Relationship Id="rId{index + 10}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
            for index, (name, _) in enumerate(media, 1)
        )
        + "</Relationships>"
    )
    temporary = target.with_suffix(".docx.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", root_rels)
        package.writestr("word/document.xml", document)
        package.writestr("word/styles.xml", _styles_xml())
        package.writestr("word/footer1.xml", _FOOTER)
        package.writestr("word/_rels/document.xml.rels", doc_rels)
        for name, data in media:
            package.writestr(f"word/media/{name}", data)
    temporary.replace(target)  # tulis atomik: Word yang sedang terbuka tidak menerima file setengah jadi
