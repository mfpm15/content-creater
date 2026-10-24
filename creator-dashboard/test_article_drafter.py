"""Tes mandiri Article Drafter (LLM palsu, tanpa jaringan). Jalankan: python creator-dashboard/test_article_drafter.py"""
import json
import struct
import sys
import tempfile
import threading
import time
import zipfile
import zlib
from pathlib import Path
from xml.dom import minidom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import article_drafter as ad  # noqa: E402

ad.RETRY_BASE_SECONDS = 0  # tes tidak perlu menunggu


def png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x7c\x8c\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def words(n: int) -> str:
    return " ".join(["kata"] * n)


OUTLINE = {
    "title": "Phishing & Smishing: <apa bedanya>",
    "abstract": "Abstrak singkat.",
    "keywords": ["phishing", "smishing"],
    "sections": [
        {"heading": "1. Pendahuluan", "goal": "latar", "subheadings": ["Latar"], "words": 100},
        {"heading": "Pembahasan", "goal": "isi", "subheadings": [], "words": 100},
        {"heading": "Kesimpulan", "goal": "tutup", "subheadings": [], "words": 100},
    ],
    "images": [
        {"id": "Alur Login!", "purpose": "alur", "aspect": "16:9", "section": 1},
        {"id": "Alur Login!", "purpose": "duplikat", "aspect": "1:1", "section": 1},
        {"id": "gambar-dua", "purpose": "kedua", "aspect": "7:3", "section": 99},
        {"id": "gambar-tiga", "purpose": "kelebihan dari image_count", "aspect": "1:1", "section": 0},
    ],
}
REFS = {"references": ["A. Penulis, Judul, 2020.", "B. Penulis, Judul, 2021."], "suggested": ["Standar X [periksa]."]}
SECTION = {"blocks": [
    {"type": "h2", "text": "diturunkan jadi h3"},
    {"type": "p", "text": "Teks **tebal** & < > rujukan [1] dan [2], hantu [9], tahun [2024]."},
    {"type": "evil", "text": "dibuang"},
    {"type": "image", "id": "Alur Login!", "caption": "Alur [1]"},
    {"type": "image", "id": "tidak-ada", "caption": "dibuang"},
    {"type": "table", "header": ["A", "B"], "rows": [["1"], ["2", "3", "lebih"]]},
]}
PROMPTS = {"images": [{"id": "alur-login", "alt": "Diagram alur", "prompt": "A clean infographic"},
                      {"id": "gambar-dua", "alt": "Kedua", "prompt": "Second image"}]}

calls = {"section": 0, "fail_section": None}
lock = threading.Lock()


def fake_chat(messages):
    system, user = messages[0]["content"], messages[-1]["content"]
    if system.startswith("TAHAP: OUTLINE"):
        return "```json\n" + json.dumps(OUTLINE) + "\n```"
    if system.startswith("TAHAP: REFERENSI"):
        return json.dumps(REFS)
    if system.startswith("TAHAP: BAGIAN"):
        with lock:
            calls["section"] += 1
        if calls["fail_section"] and f"BAGIAN NOMOR: {calls['fail_section']}" in user:
            raise ad.LLMError("LLM mati (simulasi)")
        return json.dumps(SECTION)
    if system.startswith("TAHAP: PERLUAS"):
        return json.dumps({"blocks": [{"type": "p", "text": "tambahan"}]})
    if system.startswith("TAHAP: GAMBAR"):
        return json.dumps(PROMPTS)
    raise AssertionError("tahap tidak dikenal: " + system[:30])


with tempfile.TemporaryDirectory() as tmp:
    ad.ARTICLES_DIR = Path(tmp) / "articles"
    ad._chat = fake_chat

    # input di batas kepercayaan
    for bad in (None, {}, {"points": "   "}, {"points": "x" * (ad.MAX_FIELD + 1)}, {"points": "x", "words": "abc"}):
        try:
            ad.clean_input(bad)
            raise SystemExit(f"input tidak valid lolos: {bad!r:.40}")
        except ValueError:
            pass
    big = ad.clean_input({"points": "x", "words": 15000, "image_count": 99, "article_type": "ngawur", "language": "Klingon"})
    assert big["words"] == 15000, "15.000 kata harus diterima"
    assert big["image_count"] == ad.MAX_IMAGES and big["article_type"] == ad.DEFAULT_TYPE and big["language"] == "Indonesia"
    assert ad.clean_input({"points": "x", "words": 999999})["words"] == ad.MAX_WORDS

    # gaya acak: tiap gambar dapat gaya dari preset, dan tidak semuanya sama
    images = [{"id": str(i)} for i in range(5)]
    ad.assign_styles(images, ad.RANDOM_STYLE)
    assert all(i["style"] in ad.STYLE_PRESETS for i in images) and len({i["style"] for i in images}) == 5
    fixed = [{"id": "a"}, {"id": "b"}]
    ad.assign_styles(fixed, "gaya khusus")
    assert {i["style"] for i in fixed} == {"gaya khusus"}

    # pipeline lengkap
    article = ad.generate({
        "points": "poin", "title": "Judul", "words": 300, "image_count": 2, "image_style": ad.RANDOM_STYLE,
        "sources": "A. Penulis ...", "suggest_refs": "on", "article_type": "analisis"})
    slug = article["slug"]
    assert article["complete"] and article["referencesCount"] == 2
    assert [i["id"] for i in article["images"]] == ["alur-login", "gambar-dua"], article["images"]  # duplikat & kelebihan dibuang
    assert article["images"][1]["aspect"] == "16:9" and article["images"][1]["section"] == 2  # rasio/indeks liar dirapikan
    assert all(i["style"] in ad.STYLE_PRESETS for i in article["images"])
    assert "image-prompts.md" in article["files"] and "article.docx" in article["files"]

    md = article["markdown"]
    assert md.startswith("# Phishing & Smishing")
    assert "## Abstrak" in md and "**Kata kunci:** phishing; smishing" in md  # struktur ilmiah
    assert "## 1. Pendahuluan" in md and "## 2. Pembahasan" in md and "### 1.1 diturunkan jadi h3" in md  # penomoran, nomor ganda dibuang
    assert "## Daftar Pustaka" in md and "[1] A. Penulis, Judul, 2020." in md
    assert "Rujukan yang Disarankan (Belum Diverifikasi)" in md and "Standar X [periksa]" in md
    assert "[1] dan [2]" in md and "[9]" not in md and "[PERLU VERIFIKASI]" in md and "[2024]" in md  # sitasi divalidasi
    assert "evil" not in md and "dibuang" not in md
    assert "![Diagram alur](images/alur-login.png)" in md
    assert "| 1 |  |" in md and "lebih" not in md
    assert "Daftar Isi" not in md  # 300 kata: tidak perlu daftar isi

    directory = ad.ARTICLES_DIR / slug

    def check_docx() -> str:
        with zipfile.ZipFile(directory / "article.docx") as package:
            assert package.testzip() is None
            for name in package.namelist():
                if name.endswith((".xml", ".rels")):
                    minidom.parseString(package.read(name))  # XML harus well-formed
            return package.read("word/document.xml").decode("utf-8")

    xml = check_docx()
    assert "&lt;apa bedanya&gt;" in xml and "&amp;" in xml
    assert "[GAMBAR: alur-login]" in xml and "<w:drawing>" not in xml
    assert "Daftar Pustaka" in xml and "Abstrak" in xml
    with zipfile.ZipFile(directory / "article.docx") as package:
        assert "word/footer1.xml" in package.namelist()  # nomor halaman

    # daftar isi muncul untuk artikel panjang
    long_article = ad.generate({"points": "poin", "words": 15000, "image_count": 0})
    assert "## Daftar Isi" in long_article["markdown"] and "- 1. Pendahuluan" in long_article["markdown"]

    # unggah gambar
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
    assert ad.save_image(slug, "alur-login", png(40, 20))["images"][0]["hasFile"]
    xml = check_docx()
    assert "<w:drawing>" in xml and "[GAMBAR: alur-login]" not in xml

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

    # gagal di tengah -> hasil bagian lain tersimpan; lanjutkan hanya menulis bagian yang gagal
    calls.update(section=0, fail_section="2")
    partial = ad.create({"points": "poin", "words": 300, "image_count": 0})
    try:
        ad.run_pipeline(partial)
        raise SystemExit("kegagalan bagian tidak dilaporkan")
    except ad.LLMError as exc:
        assert "Lanjutkan" in str(exc)
    state = ad.get_article(partial)
    assert not state["complete"] and state["sectionsDone"] == 2 and state["sectionsTotal"] == 3
    calls.update(section=0, fail_section=None)
    done = ad.run_pipeline(partial)
    assert done["complete"] and calls["section"] == 1, "lanjutkan harus menulis ulang hanya 1 bagian"

    # job latar belakang
    job = ad.start_job({"points": "poin", "words": 300, "image_count": 0})
    for _ in range(100):
        status = ad.job_status(job["id"])
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    assert ad.get_article(status["slug"])["complete"]
    assert any(item["slug"] == status["slug"] and item["complete"] for item in ad.list_articles())

    # galat LLM terus-menerus -> job berstatus error dan pesan terbaca
    def broken(messages):
        raise ad.LLMError("LLM tidak terjangkau (simulasi)")

    ad._chat = broken
    job = ad.start_job({"points": "poin", "words": 300})
    for _ in range(100):
        status = ad.job_status(job["id"])
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "error" and "tidak terjangkau" in status["error"], status

    # LLM mengembalikan sampah -> LLMError
    ad._chat = lambda messages: "bukan json"
    try:
        ad.make_outline(ad.clean_input({"points": "x"}))
        raise SystemExit("sampah LLM lolos")
    except ad.LLMError:
        pass

print("Article Drafter test passed")
