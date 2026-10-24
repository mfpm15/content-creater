"""Tes mandiri Article Drafter (tanpa LLM asli, tanpa jaringan). Jalankan: python creator-dashboard/test_article_drafter.py"""
import json
import struct
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from xml.dom import minidom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import article_drafter as ad  # noqa: E402


def png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x7c\x8c\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


LLM_OUTPUT = """```json
{"title": "Phishing & Smishing: <apa bedanya>", "summary": "Ringkasan **singkat**.",
 "blocks": [
  {"type": "h2", "text": "Pengantar"},
  {"type": "p", "text": "Teks dengan **tebal** dan simbol & < > \\" ."},
  {"type": "bullets", "items": ["satu", "dua"]},
  {"type": "evil", "text": "harus dibuang"},
  {"type": "image", "id": "Alur Login!", "caption": "Alur login"},
  {"type": "image", "id": "tidak-ada", "caption": "harus dibuang"},
  {"type": "callout", "title": "Catatan", "text": "Hati-hati | pipa"},
  {"type": "table", "header": ["A", "B"], "rows": [["1"], ["2", "3", "kelebihan"]]}
 ],
 "images": [
  {"id": "Alur Login!", "purpose": "jelaskan alur", "alt": "Diagram alur", "aspect": "16:9", "prompt": "A clean flat infographic ..."},
  {"id": "Alur Login!", "purpose": "duplikat", "alt": "x", "aspect": "1:1", "prompt": "dup"}
 ]}
```"""

with tempfile.TemporaryDirectory() as tmp:
    ad.ARTICLES_DIR = Path(tmp) / "articles"
    ad._chat = lambda messages: LLM_OUTPUT  # LLM palsu

    # validasi input di batas kepercayaan
    for bad in (None, {}, {"points": "   "}, {"points": "x" * (ad.MAX_FIELD + 1)}):
        try:
            ad.clean_input(bad)
            raise SystemExit(f"input tidak valid lolos: {bad!r:.40}")
        except ValueError:
            pass

    article = ad.generate({"points": "poin 1\npoin 2", "title": "Judul", "image_count": 1})
    slug = article["slug"]
    assert [i["id"] for i in article["images"]] == ["alur-login"], article["images"]  # id dirapikan, duplikat dibuang
    assert not article["images"][0]["hasFile"]
    assert "image-prompts.md" in article["files"] and "article.docx" in article["files"]

    md = article["markdown"]
    assert "evil" not in md and "harus dibuang" not in md  # blok tak dikenal dan gambar yatim dibuang
    assert "![Diagram alur](images/alur-login.png)" in md
    assert "| 1 |  |" in md and "kelebihan" not in md  # baris tabel diratakan sesuai header

    directory = ad.ARTICLES_DIR / slug

    def check_docx() -> str:
        path = directory / "article.docx"
        with zipfile.ZipFile(path) as package:
            assert package.testzip() is None
            for name in package.namelist():
                if name.endswith((".xml", ".rels")):
                    minidom.parseString(package.read(name))  # XML harus well-formed
            return package.read("word/document.xml").decode("utf-8")

    xml = check_docx()
    assert "&lt;apa bedanya&gt;" in xml and "&amp;" in xml  # karakter khusus di-escape
    assert "[GAMBAR: alur-login]" in xml and "<w:drawing>" not in xml  # belum ada gambar -> penanda

    # unggah gambar -> terpasang di md dan docx
    for bad in (b"bukan gambar", b"\x89PNG\r\n\x1a\n" + b"rusak"):
        try:
            ad.save_image(slug, "alur-login", bad)
            raise SystemExit("gambar tidak valid lolos")
        except ValueError:
            pass
    try:
        ad.save_image(slug, "../../etc", png(2, 1))
        raise SystemExit("id gambar liar lolos")
    except ValueError:
        pass
    updated = ad.save_image(slug, "alur-login", png(40, 20))
    assert updated["images"][0]["hasFile"]
    xml = check_docx()
    assert "<w:drawing>" in xml and "[GAMBAR:" not in xml
    with zipfile.ZipFile(directory / "article.docx") as package:
        assert any(n.startswith("word/media/image1") for n in package.namelist())

    # path traversal
    for bad_slug in ("../x", "..", "a/b", "A"):
        try:
            ad.get_article(bad_slug)
            raise SystemExit(f"slug liar lolos: {bad_slug}")
        except (ValueError, FileNotFoundError):
            pass
    try:
        ad.read_file(slug, "../input.json")
        raise SystemExit("unduhan liar lolos")
    except FileNotFoundError:
        pass

    # LLM mengembalikan sampah dua kali -> LLMError, tidak ada folder setengah jadi
    ad._chat = lambda messages: "bukan json"
    before = len(ad.list_articles())
    try:
        ad.generate({"points": "x"})
        raise SystemExit("sampah LLM lolos")
    except ad.LLMError:
        pass
    assert len(ad.list_articles()) == before

print("Article Drafter test passed")
