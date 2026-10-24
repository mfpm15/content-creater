"""Article Drafter: poin-poin draft -> artikel (.md + .docx) + prompt gambar.

Gambar tidak dibuat di sini. Tool menghasilkan prompt untuk Nano Banana / ChatGPT;
hasil gambar diunggah kembali lalu .md dan .docx dibangun ulang dengan gambar tertanam.
Hanya stdlib. .docx ditulis langsung sebagai paket OOXML.
"""
from __future__ import annotations

import json
import os
import re
import struct
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "output" / "articles"
LLM_URL = os.getenv("ARTICLE_LLM_BASE_URL", "http://localhost:20128/v1").rstrip("/")
LLM_MODEL = os.getenv("ARTICLE_LLM_MODEL", "ag/gemini-3.8-flash-high")
LLM_KEY = os.getenv("ARTICLE_LLM_API_KEY", "9router-local")
LLM_TIMEOUT = int(os.getenv("ARTICLE_LLM_TIMEOUT", "240"))

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DOWNLOADS = {
    "article.md": "text/markdown; charset=utf-8",
    "article.docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image-prompts.md": "text/markdown; charset=utf-8",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FIELD = 20000


class LLMError(RuntimeError):
    pass


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


def _clean_id(value: object) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(value or "").lower()).strip("-")[:40]


def _s(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _str_list(value: object) -> list[str]:
    return [_s(item) for item in value if _s(item)] if isinstance(value, list) else []


def normalize(raw: object, fallback_title: str) -> dict:
    """Validasi keluaran LLM (batas kepercayaan): buang blok tak dikenal, rapikan id gambar."""
    if not isinstance(raw, dict):
        raise ValueError("keluaran bukan objek JSON")
    images: list[dict] = []
    seen: set[str] = set()
    for item in raw.get("images") or []:
        if not isinstance(item, dict):
            continue
        image_id = _clean_id(item.get("id"))
        if not ID_RE.match(image_id) or image_id in seen:
            continue
        seen.add(image_id)
        images.append({
            "id": image_id,
            "purpose": _s(item.get("purpose")),
            "alt": _s(item.get("alt")) or image_id,
            "aspect": _s(item.get("aspect")) or "16:9",
            "prompt": _s(item.get("prompt")),
        })
    blocks: list[dict] = []
    for block in raw.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind in ("h2", "h3", "p"):
            if _s(block.get("text")):
                blocks.append({"type": kind, "text": _s(block["text"])})
        elif kind in ("bullets", "numbered"):
            items = _str_list(block.get("items"))
            if items:
                blocks.append({"type": kind, "items": items})
        elif kind == "callout":
            if _s(block.get("text")):
                blocks.append({"type": "callout", "title": _s(block.get("title")), "text": _s(block["text"])})
        elif kind == "table":
            header = _str_list(block.get("header"))
            rows = [[_s(c) for c in row] for row in (block.get("rows") or []) if isinstance(row, list)]
            if header and rows:
                rows = [(row + [""] * len(header))[:len(header)] for row in rows]
                blocks.append({"type": "table", "header": header, "rows": rows})
        elif kind == "image":
            image_id = _clean_id(block.get("id"))
            if image_id in seen:
                blocks.append({"type": "image", "id": image_id, "caption": _s(block.get("caption"))})
    if not blocks:
        raise ValueError("artikel kosong")
    return {
        "title": _s(raw.get("title")) or fallback_title,
        "summary": _s(raw.get("summary")),
        "blocks": blocks,
        "images": images,
    }


SYSTEM_PROMPT = """Kamu penulis artikel profesional. Balas HANYA dengan satu objek JSON valid, tanpa teks lain, dengan bentuk:
{"title": str, "summary": str,
 "blocks": [ {"type":"h2","text":str} | {"type":"h3","text":str} | {"type":"p","text":str}
           | {"type":"bullets","items":[str]} | {"type":"numbered","items":[str]}
           | {"type":"callout","title":str,"text":str}
           | {"type":"table","header":[str],"rows":[[str]]}
           | {"type":"image","id":"kebab-case","caption":str} ],
 "images": [ {"id":"kebab-case","purpose":str,"alt":str,"aspect":"16:9|1:1|4:3|9:16","prompt":str} ]}
Aturan:
- Isi artikel HANYA dari poin dan sumber yang diberikan pengguna. Jangan mengarang fakta, angka, nama, atau kutipan. Bagian yang butuh fakta tetapi tidak ada sumbernya: tulis [PERLU VERIFIKASI].
- Teks polos. Satu-satunya format inline yang boleh: **tebal**.
- Blok image menunjuk ke entri images dengan id sama. Setiap entri images dipakai oleh tepat satu blok image.
- Setiap "prompt" gambar: bahasa Inggris, mandiri (bisa langsung ditempel ke generator gambar), sebut subjek, komposisi, gaya visual, palet warna, rasio, dan teks yang tampil di dalam gambar (dalam bahasa yang diminta, dieja persis, singkat). Tanpa watermark dan tanpa logo merek.
- Jumlah gambar tepat sesuai permintaan. Jika 0, images kosong dan tidak ada blok image."""


def build_user_prompt(inp: dict) -> str:
    parts = [
        f"Judul kerja: {inp['title'] or '(usulkan judul sendiri)'}",
        f"Audiens: {inp['audience'] or 'umum'}",
        f"Bahasa artikel: {inp['language']}",
        f"Nada: {inp['tone']}",
        f"Panjang target: sekitar {inp['words']} kata",
        f"Jumlah gambar: {inp['image_count']}",
        f"Gaya visual gambar: {inp['image_style']}",
        f"Bahasa teks di dalam gambar: {inp['image_text_language']}",
        "",
        "POIN DRAFT DARI PENGGUNA:",
        inp["points"],
    ]
    if inp["sources"]:
        parts += ["", "SUMBER / CATATAN YANG BOLEH DIPAKAI:", inp["sources"]]
    if inp["image_requests"]:
        parts += ["", "PERMINTAAN GAMBAR (satu per baris; wujudkan sebagai gambar):", inp["image_requests"]]
    return "\n".join(parts)


def clean_input(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("input harus objek JSON")

    def text(key: str, default: str = "") -> str:
        value = raw.get(key)
        value = value.strip() if isinstance(value, str) else default
        if len(value) > MAX_FIELD:
            raise ValueError(f"Field '{key}' terlalu panjang (maks {MAX_FIELD} karakter)")
        return value

    inp = {
        "title": text("title"),
        "audience": text("audience"),
        "language": text("language", "Indonesia"),
        "tone": text("tone", "semi-formal"),
        "words": min(max(int(raw.get("words") or 1200), 200), 6000),
        "points": text("points"),
        "sources": text("sources"),
        "image_count": min(max(int(raw.get("image_count") or 0), 0), 8),
        "image_requests": text("image_requests"),
        "image_style": text("image_style", "infografis bersih, flat, palet biru-ungu"),
        "image_text_language": text("image_text_language", "Indonesia"),
    }
    if not inp["points"]:
        raise ValueError("Poin draft wajib diisi")
    return inp


def slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "artikel"
    return f"{base}-{time.strftime('%m%d-%H%M%S')}"


def generate(raw_input: object) -> dict:
    inp = clean_input(raw_input)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": build_user_prompt(inp)}]
    last_error = ""
    for attempt in range(2):
        content = _chat(messages)
        try:
            article = normalize(_extract_json(content), inp["title"] or "Artikel")
            break
        except ValueError as exc:  # JSON.JSONDecodeError subclass ValueError
            last_error = str(exc)
            messages = messages + [
                {"role": "assistant", "content": content[:4000]},
                {"role": "user", "content": f"Keluaran tidak valid ({last_error}). Balas ulang HANYA dengan objek JSON yang benar."},
            ]
    else:
        raise LLMError(f"LLM tidak menghasilkan JSON yang valid setelah 2 percobaan: {last_error}")
    slug = slugify(article["title"])
    directory = ARTICLES_DIR / slug
    (directory / "images").mkdir(parents=True, exist_ok=True)
    (directory / "input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "article.json").write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    build_outputs(slug)
    return get_article(slug)


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
    article = json.loads((directory / "article.json").read_text(encoding="utf-8"))
    images = [
        {**image, "hasFile": find_image(directory, image["id"]) is not None}
        for image in article["images"]
    ]
    return {
        "slug": slug,
        "title": article["title"],
        "summary": article["summary"],
        "images": images,
        "markdown": (directory / "article.md").read_text(encoding="utf-8"),
        "files": [name for name in DOWNLOADS if (directory / name).is_file()],
        "path": str(directory),
    }


def list_articles() -> list[dict]:
    if not ARTICLES_DIR.is_dir():
        return []
    items = []
    for directory in sorted(ARTICLES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = directory / "article.json"
        if directory.is_dir() and meta.is_file():
            try:
                title = json.loads(meta.read_text(encoding="utf-8")).get("title", directory.name)
            except ValueError:
                continue
            items.append({"slug": directory.name, "title": title})
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
    article = json.loads((directory / "article.json").read_text(encoding="utf-8"))
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
    article = json.loads((directory / "article.json").read_text(encoding="utf-8"))
    (directory / "article.md").write_text(to_markdown(article, directory), encoding="utf-8")
    (directory / "image-prompts.md").write_text(to_prompts_markdown(article), encoding="utf-8")
    to_docx(article, directory, directory / "article.docx")
    return get_article(slug)


# ---------------------------------------------------------------------- Markdown

def to_markdown(article: dict, directory: Path | None = None) -> str:
    images = {image["id"]: image for image in article["images"]}
    lines = [f"# {article['title']}", ""]
    if article["summary"]:
        lines += [f"> {article['summary']}", ""]
    for block in article["blocks"]:
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


def to_docx(article: dict, directory: Path, target: Path) -> None:
    images = {image["id"]: image for image in article["images"]}
    media: list[tuple[str, bytes]] = []  # (nama file di paket, isi)
    body: list[str] = [_p(_runs(article["title"]), "Title")]
    if article["summary"]:
        body.append(_p(_runs(article["summary"], italic=True, color="5A607F")))
    for block in article["blocks"]:
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
    section = (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
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
        package.writestr("word/_rels/document.xml.rels", doc_rels)
        for name, data in media:
            package.writestr(f"word/media/{name}", data)
    temporary.replace(target)  # tulis atomik: Word yang sedang terbuka tidak menerima file setengah jadi
