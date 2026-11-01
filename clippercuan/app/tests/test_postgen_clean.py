"""Judul tidak boleh ikut masuk ke caption/deskripsi (kasus nyata: YouTube Shorts menampilkan 'Judul: ...' di deskripsi)."""
from clipper import postgen

TITLE = "How Marcus Hutchins Stopped WannaCry Ransomware"
BODY = ("Marcus Hutchins stopped the 2017 WannaCry outbreak by registering an obscure domain hardcoded into the malware. "
        "Once the site was live, the ransomware ceased replicating.")


def test_labelled_title_line_is_removed_exactly_like_user_report():
    text = f"Judul: {TITLE}\n\n{BODY}\n\nShare your take in the comments."
    out = postgen.clean_caption(text, TITLE)
    assert "Judul:" not in out and out.startswith("Marcus Hutchins stopped")
    assert out.endswith("Share your take in the comments.")


def test_variants_of_label_and_bare_title_line():
    for label in ("Judul", "judul video", "Title", "HEADLINE"):
        assert postgen.clean_caption(f"{label}: {TITLE}\n{BODY}", TITLE) == BODY
    assert postgen.clean_caption(f"{TITLE}\n\n{BODY}", TITLE) == BODY            # judul polos di baris pertama
    assert postgen.clean_caption(f"{TITLE.lower()}!\n\n{BODY}", TITLE) == BODY   # beda huruf/tanda baca


def test_real_content_is_never_removed():
    kept = f"{BODY}\n\nJudulnya menarik, bukan?"            # 'Judul' di tengah kalimat bukan label
    assert postgen.clean_caption(kept, TITLE) == kept
    mid = f"{BODY}\n{TITLE}\nCatatan akhir."                # judul di tengah isi = kutipan sah, bukan baris pembuka
    assert TITLE in postgen.clean_caption(mid, TITLE)
    assert postgen.clean_caption("", TITLE) == "" and postgen.clean_caption(None, "") == ""


def test_local_package_has_no_title_in_any_platform_caption():
    pkg = postgen.local(BODY, TITLE, "review", "en")
    for name, p in pkg["platforms"].items():
        assert "Judul:" not in p["caption"] and "Judul:" not in p["ready"], name
    assert pkg["platforms"]["youtube_shorts"]["title"].startswith(TITLE[:20])       # judul tetap ada di kolomnya sendiri


def test_assemble_cleans_llm_output_that_repeats_the_title():
    p = postgen._assemble(TITLE, f"Judul: {TITLE}\n\n{BODY}", "Share your take.", ["#cybersecurity"], "youtube_shorts")
    assert "Judul:" not in p["ready"] and BODY in p["ready"] and p["title"].startswith(TITLE[:20])
