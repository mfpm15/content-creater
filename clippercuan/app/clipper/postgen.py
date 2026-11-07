"""Generator caption siap posting per profil konten & platform.

Output satu paket: judul, caption TikTok / YouTube Shorts / Instagram Reels, hashtag, CTA, dan
teks siap salin. LLM (rantai GPT-5.6 Think Deeper + Claude) dipakai bila aktif; bila gagal, versi
lokal berbasis aturan tetap menghasilkan teks yang bisa langsung diposting.

Aturan: klaim hanya dari transkrip, tanpa engagement bait palsu, hashtag 3-6 relevan (bukan spam).
"""
from __future__ import annotations

import re

PLATFORMS = {
    "tiktok": {"label": "TikTok", "max_chars": 2200, "tags": 5},
    "youtube_shorts": {"label": "YouTube Shorts", "max_chars": 5000, "title_max": 100, "tags": 3},
    "instagram_reels": {"label": "Instagram Reels", "max_chars": 2200, "tags": 6},
}

# Gaya Indonesia/Melayu. Template Inggris dipisahkan agar satu caption tidak pernah mencampur bahasa.
STYLE = {
    "podcast": {"tone": "insight & cerita, kutip inti pendapat narasumber", "emoji": "🎙️",
                "hook": "Pendapat ini bikin mikir: {t}",
                "cta": "Setuju atau nggak? Tulis pendapatmu di komentar.",
                "tags": ["#podcast", "#podcastindonesia", "#insight"]},
    "interview": {"tone": "tanya-jawab utuh, sebut konteks pertanyaan", "emoji": "🎤",
                  "hook": "Pertanyaannya simpel, jawabannya dalam: {t}",
                  "cta": "Kamu bakal jawab apa?", "tags": ["#interview", "#wawancara", "#insight"]},
    "review": {"tone": "verdict jujur: masalah, kelebihan/kekurangan, value", "emoji": "🔍",
               "hook": "Jujur soal ini: {t}",
               "cta": "Mau dibahas produk apa lagi? Tulis di komentar.",
               "tags": ["#review", "#reviewjujur", "#rekomendasi"]},
    "tech_review": {"tone": "spesifikasi & demo hanya dari transkrip, verdict jelas", "emoji": "📱",
                    "hook": "Sebelum beli, tonton ini: {t}",
                    "cta": "Tim worth it atau skip? Komen di bawah.",
                    "tags": ["#techreview", "#gadget", "#teknologi"]},
    "gaming": {"tone": "energik, momen clutch/outplay/reaksi", "emoji": "🎮",
                "hook": "Momen ini nggak ada obat: {t}",
                "cta": "Kamu bakal ambil keputusan yang sama?",
                "tags": ["#gaming", "#gamer", "#gameplay"]},
    "mobile_legends": {"tone": "bahasa player MLBB, sebut role/objective HANYA jika ada di transkrip", "emoji": "⚔️",
                       "hook": "Player MLBB wajib lihat ini: {t}",
                       "cta": "Main role apa kamu? Tag duo mabarmu.",
                       "tags": ["#mobilelegends", "#mlbb", "#mlbbindonesia"]},
    "educational": {"tone": "hasil belajar jelas, langkah ringkas", "emoji": "💡",
                    "hook": "Dalam 1 menit kamu bakal paham: {t}",
                    "cta": "Simpan biar nggak lupa.", "tags": ["#belajar", "#edukasi", "#tips"]},
    "general": {"tone": "value-first, ringkas", "emoji": "✨", "hook": "{t}",
                "cta": "Bagian mana yang paling relevan buatmu?", "tags": ["#fyp", "#viral"]},
}
STYLE_EN = {
    "podcast": {"tone": "insight and story; quote the speaker's central point", "emoji": "🎙️",
                "hook": "A thought-provoking take: {t}", "cta": "What do you think? Share your view in the comments.",
                "tags": ["#podcast", "#insight", "#discussion"]},
    "interview": {"tone": "complete question and answer with context", "emoji": "🎤",
                  "hook": "A simple question with a deeper answer: {t}", "cta": "How would you answer it?",
                  "tags": ["#interview", "#conversation", "#insight"]},
    "review": {"tone": "honest verdict with tradeoffs and value", "emoji": "🔍", "hook": "The honest view: {t}",
               "cta": "What should be reviewed next?", "tags": ["#review", "#verdict", "#recommendation"]},
    "tech_review": {"tone": "specifications and demonstrations grounded in the transcript", "emoji": "📱",
                     "hook": "Watch this before you buy: {t}", "cta": "Worth it or skip it? Share your take.",
                     "tags": ["#techreview", "#technology", "#gadgets"]},
    "gaming": {"tone": "energetic clutch, outplay, and reaction moments", "emoji": "🎮",
               "hook": "This moment was unreal: {t}", "cta": "Would you make the same move?",
               "tags": ["#gaming", "#gamer", "#gameplay"]},
    "mobile_legends": {"tone": "MLBB terminology only when supported by the transcript", "emoji": "⚔️",
                       "hook": "MLBB players need to see this: {t}", "cta": "What role do you play?",
                       "tags": ["#mobilelegends", "#mlbb", "#gaming"]},
    "educational": {"tone": "clear learning outcome and concise steps", "emoji": "💡",
                    "hook": "Understand this in under a minute: {t}", "cta": "Save this for later.",
                    "tags": ["#learning", "#education", "#tips"]},
    "general": {"tone": "concise and value-first", "emoji": "✨", "hook": "{t}",
                "cta": "Which part was most useful to you?", "tags": ["#shortvideo", "#insight"]},
}
FORMAT_TAG = {"tiktok": "#fyp", "youtube_shorts": "#shorts", "instagram_reels": "#reels"}


def _language_code(language: str | None) -> str:
    """Normalisasi bahasa keluaran. Auto sudah diganti bahasa hasil deteksi sebelum fungsi ini dipanggil."""
    value = str(language or "id").lower().split("-", 1)[0]
    return "id" if value in {"id", "ms"} else "en" if value == "en" else value


def _style(profile: str | None, language: str | None = "id") -> dict:
    styles = STYLE_EN if _language_code(language) == "en" else STYLE
    return styles.get(profile or "general", styles["general"])


def _tag(word: str) -> str:
    w = re.sub(r"[^\w]", "", word, flags=re.U)
    return f"#{w.lower()}" if w else ""


def _uniq(items):
    out = []
    for x in items:
        if x and x.lower() not in {o.lower() for o in out}:
            out.append(x)
    return out


def _first_sentence(text: str, limit: int = 140) -> str:
    s = re.split(r"(?<=[.!?])\s+", (text or "").strip())[0] if text else ""
    return (s[:limit].rsplit(" ", 1)[0] + "…") if len(s) > limit else s


_LABEL = re.compile(r"^\s*(?:judul(?:\s+video)?|title|headline)\s*[:：\-–]\s*", re.I)


def clean_caption(body: str, title: str = "") -> str:
    """Buang judul yang ikut masuk ke isi caption/deskripsi.

    Judul punya kolom sendiri di YouTube; kalau ikut di deskripsi ia tampil dua kali. Yang dibuang: baris berlabel
    ('Judul: ...', 'Title: ...') dan baris pembuka yang sama persis dengan judul. Isi lain tidak disentuh.
    """
    norm = lambda s: re.sub(r"\W+", " ", s or "", flags=re.U).strip().casefold()
    want = norm(title)
    lines = (body or "").replace("\r", "").split("\n")
    out = []
    for i, ln in enumerate(lines):
        if _LABEL.match(ln):
            continue
        if want and norm(ln) == want and not any(x.strip() for x in out):
            continue
        out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _assemble(title: str, body: str, cta: str, tags: list[str], platform: str) -> dict:
    spec = PLATFORMS[platform]
    tags = _uniq(tags + [FORMAT_TAG[platform]])[: spec["tags"]]
    body = clean_caption(body, title)
    caption = "\n\n".join(p for p in (body.strip(), cta.strip()) if p)
    ready = (caption + "\n\n" + " ".join(tags)).strip()[: spec["max_chars"]]
    out = {"caption": caption, "hashtags": tags, "ready": ready}
    if platform == "youtube_shorts":
        out["title"] = (title.strip() + " #shorts")[: spec["title_max"]]
    return out


def local(text: str, title: str, profile: str = "general", language: str | None = None) -> dict:
    """Tanpa AI: template per profil + kata kunci transkrip."""
    from .highlights import STOP, _tokens, title_options
    st = _style(profile, language)
    toks = [t for t in _tokens(text or "") if len(t) > 3 and t not in STOP and not t.isdigit()]
    freq: dict[str, float] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1 + (.5 if len(t) > 6 else 0)
    topic = [_tag(k) for k, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:3]]
    tags = _uniq(st["tags"][:2] + topic + st["tags"][2:])
    fallback_title = "Key moment" if _language_code(language) == "en" else "Momen penting"
    head = (title or _first_sentence(text, 70) or fallback_title).strip()
    hook = f"{st['emoji']} " + st["hook"].format(t=head)
    quote = _first_sentence(text)
    body = hook + (f"\n\n\"{quote}\"" if quote and quote.lower() != head.lower() else "")
    cta = st["cta"]
    return _package(head, {p: _assemble(head, body, cta, tags, p) for p in PLATFORMS},
                     tags, cta, title_options(text or head), profile, "lokal")


def _package(title, platforms, tags, cta, titles, profile, engine) -> dict:
    main = platforms["tiktok"]
    return {"caption": main["caption"], "hashtags": tags[:6], "cta": cta, "title": title,
            "title_options": titles[:3], "platforms": platforms, "profile": profile, "engine": engine,
            "hashtag_groups": {"niche": tags[:2], "topic": tags[2:5], "format": [FORMAT_TAG["tiktok"]]}}


def _llm(text: str, title: str, profile: str, language: str | None) -> dict:
    from . import llm
    lang = _language_code(language)
    st = _style(profile, lang)
    language_name = {"en": "English only", "id": "Bahasa Indonesia saja"}.get(lang, f"bahasa {lang} saja")
    user = (
        f"Profil konten: {profile} (gaya: {st['tone']}).\nJudul klip: {title}\nTranskrip klip:\n{(text or '')[:3000]}\n\n"
        f"Buat paket posting SIAP SALIN dalam {language_name}. SELURUH hook, isi, CTA, dan hashtag harus satu bahasa; "
        "jangan mencampur bahasa template dengan bahasa transkrip. Aturan: klaim hanya dari transkrip; "
        "hook 1 baris di awal; 1-3 kalimat isi; CTA natural (bukan 'like & follow'); emoji maksimal 2; hashtag relevan tanpa spam. "
        "TikTok: santai, 3-5 hashtag. YouTube Shorts: judul <=90 karakter + deskripsi 1-2 kalimat, 3 hashtag. "
        "Instagram Reels: caption sedikit lebih panjang dengan jeda baris, 4-6 hashtag.\n"
        'Format JSON: {"title":"...","title_options":["...","...","..."],"cta":"...",'
        '"tiktok":{"caption":"...","hashtags":["#..."]},"youtube_shorts":{"title":"...","caption":"...","hashtags":["#..."]},'
        '"instagram_reels":{"caption":"...","hashtags":["#..."]}}')
    out, model = llm.chat_chain("posts", llm.SYS_EDITOR, user, max_tokens=2500)
    if not isinstance(out, dict):
        raise llm.LLMError("Format paket posting tidak valid")
    head = str(out.get("title") or title).strip()[:90]
    cta = str(out.get("cta", "")).strip()[:200]
    platforms, all_tags = {}, []
    for p in PLATFORMS:
        d = out.get(p) or {}
        tags = [str(h).strip() for h in d.get("hashtags", []) if str(h).strip().startswith("#")]
        if not d.get("caption"):
            raise llm.LLMError(f"Caption {p} kosong")
        all_tags += tags
        a = _assemble(str(d.get("title") or head), str(d["caption"])[:1500], "", tags or _style(profile, lang)["tags"], p)
        if p == "youtube_shorts" and d.get("title"):
            a["title"] = str(d["title"])[:100]
        platforms[p] = a
    titles = [str(t).strip()[:80] for t in out.get("title_options", []) if str(t).strip()] or [head]
    return _package(head, platforms, _uniq(all_tags), cta, titles, profile, model)


def generate(text: str, title: str, profile: str | None = "general", language: str | None = None,
             use_llm: bool = True) -> dict:
    profile = profile if profile in STYLE else "general"
    if use_llm:
        from . import llm
        if llm.active("titles") or llm.active("moments"):
            try:
                return _llm(text, title, profile, language)
            except Exception as e:  # noqa: BLE001 — selalu ada versi lokal
                res = local(text, title, profile, language)
                res["warning"] = f"AI gagal, dipakai template lokal ({str(e)[:160]})"
                return res
    return local(text, title, profile, language)
