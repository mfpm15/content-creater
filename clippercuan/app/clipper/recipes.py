"""Resep gaya viral siap pakai: satu klik mengatur durasi, format, caption, judul, dan efek.

Disusun dari pola yang terlihat pada klip short-form populer (box highlight per kata, kata kunci dengan font aksen,
judul hook dua baris, caption huruf campuran di tengah-bawah frame) dan disesuaikan dengan niche ClipperCuan.
Ini titik awal yang masuk akal, bukan jaminan viral: uji A/B dengan data unggahan sendiri.
"""
from __future__ import annotations

CAPTION_SIZE_LEVELS = {"small": 64, "medium": 72, "large": 84, "xlarge": 96}


def _clean_caption(template_id: str, size: int, style: str = "clean") -> dict:
    size_level = next((level for level, value in CAPTION_SIZE_LEVELS.items() if value == size), "custom")
    return {"enabled": True, "role": "spoken-caption", "preset": template_id, "template_id": template_id,
            "size_level": size_level, "style": style, "box": False, "effect": "none",
            "font": "Barlow Condensed", "size": size, "outline": 4, "shadow": 0, "color": "#FFFFFF",
            "highlight": "#FFD166", "uppercase": False, "words_per_line": 5, "max_chars": 30,
            "max_lines": 2, "line_height": 1.12, "safe_area": .18, "position": "bottom", "y_pct": 74,
            "animation": "none", "accent_font": "Barlow Condensed", "accent_mode": "color",
            "accent_scale": 106 if style == "keyword" else 100}


_BASE_CLEAN = {"content_profile": "auto", "duration_preset": "auto", "layout": "portrait", "smart_crop": True,
               "cut_silence": False, "caption_layers": 1, "source_has_burned_captions": "unknown",
               "title": {"enabled": False, "role": "hook", "preset": "clean", "duration": 3, "size": 58, "y_pct": 12},
               "emoji": {"enabled": False}, "progress_bar": {"enabled": False}, "cta": {"enabled": False}}

RECIPES: dict[str, dict] = {
    "recommended": {
        "label": "Clean Large", "template_name": "Clean Large", "niche": "auto", "badge": "Default · Besar",
        "tier": "primary", "experimental": False,
        "desc": "Caption putih besar, stabil, maksimal dua baris, tanpa active-word, animasi, glow, box, atau elemen dekoratif.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("clean-large", 84),
            "outline": 4, "words_per_line": 5, "max_chars": 30, "y_pct": 74}},
    },
    "clean-focus": {
        "label": "Clean Focus Large", "template_name": "Clean Focus Large", "niche": "auto", "badge": "Opsi kedua · Besar",
        "tier": "primary", "experimental": False,
        "desc": "Caption besar stabil dengan satu kata aksen sederhana dalam event glyph tunggal, tanpa layer visual duplikat.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("clean-focus-large", 84, "keyword"),
            "accent_mode": "color", "accent_scale": 106, "outline": 4, "words_per_line": 5,
            "max_chars": 30, "y_pct": 74}},
    },
    "minimal-medium": {
        "label": "Minimal Medium", "template_name": "Minimal Medium", "niche": "auto", "badge": "Pembanding · Sedang",
        "tier": "primary", "experimental": False,
        "desc": "Caption putih stabil ukuran sedang untuk pembanding keterbacaan.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("minimal-medium", 72),
            "outline": 3, "words_per_line": 5, "max_chars": 32, "y_pct": 74}},
    },
    "viral-pop": {
        "label": "Viral Pop · Eksperimental", "template_name": "Viral Pop", "niche": "advanced", "badge": "Advanced · Eksperimental",
        "tier": "advanced", "experimental": True,
        "desc": "Karaoke, pop, dan glow. Hanya opt-in; tidak pernah dipilih otomatis.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("viral-pop", 84, "karaoke"),
            "animation": "pop", "effect": "glow", "glow_color": "#FFD166", "outline": 5,
            "words_per_line": 4, "max_chars": 27, "y_pct": 72}},
    },
    "box-punch": {
        "label": "Box Punch V2", "template_name": "Box Punch V2", "niche": "advanced", "badge": "Rekomendasi kreatif · Production",
        "tier": "advanced", "experimental": False, "status": "Production",
        "desc": "Satu caption besar, maksimal dua baris, satu frasa ditekankan, masuk halus, dekorasi semantik opsional.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("box-punch-v2", 84, "box"),
            "box": True, "animation": "subtle-pop", "animation_ms": 180, "highlight": "#F4B942", "outline": 4,
            "box_padding": 10, "words_per_line": 4, "max_chars": 27, "max_lines": 2, "y_pct": 72},
            "decoration": {"mode": "none", "provenance": None, "max_active": 1}},
    },
    "neon-karaoke": {
        "label": "Neon Karaoke · Eksperimental", "template_name": "Neon Karaoke", "niche": "advanced", "badge": "Advanced · Eksperimental",
        "tier": "advanced", "experimental": True,
        "desc": "Active-word cyan, glow neon, dan pop. Hanya opt-in; tidak pernah dipilih otomatis.",
        "settings": {**_BASE_CLEAN, "caption": {**_clean_caption("neon-karaoke", 84, "karaoke"),
            "animation": "pop", "effect": "glow", "highlight": "#54E6E6", "glow_color": "#54E6E6",
            "outline": 5, "words_per_line": 4, "max_chars": 27, "y_pct": 72}},
    },
    "podcast-box": {
        "label": "Podcast · Box merah", "niche": "podcast", "badge": "Paling populer",
        "desc": "Huruf campuran, kotak merah mengikuti kata aktif, judul hook dua baris. Gaya klip podcast yang paling sering dipakai.",
        "settings": {
            "content_profile": "podcast", "duration_preset": "25-40", "layout": "portrait", "smart_crop": True, "cut_silence": True,
            "caption": {"preset": "box-merah", "style": "clean", "box": True, "effect": "none", "font": "Barlow Condensed", "size": 92,
                        "color": "#FFFFFF", "highlight": "#FF2D2D", "uppercase": False, "words_per_line": 3, "max_chars": 22,
                        "y_pct": 62, "animation": "pop"},
            "title": {"enabled": True, "role": "hook", "preset": "duo", "duration": 3, "size": 68, "accent": "#3DE0A0", "glow": "#C6FF3D", "y_pct": 12},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False},
        },
    },
    "podcast-hormozi": {
        "label": "Podcast · Hormozi", "niche": "podcast", "badge": "Bisnis & uang",
        "desc": "2 kata per layar, HURUF BESAR, kata kunci kuning berfont aksen. Cocok untuk bisnis, keuangan, motivasi.",
        "settings": {
            "content_profile": "podcast", "duration_preset": "15-25", "layout": "portrait", "smart_crop": True, "cut_silence": True,
            "caption": {"preset": "hormozi", "style": "keyword", "box": True, "effect": "none", "font": "Montserrat ExtraBold", "size": 88,
                        "color": "#FFFFFF", "highlight": "#FFC933", "uppercase": True, "words_per_line": 2, "max_chars": 18,
                        "y_pct": 58, "animation": "pop", "accent_font": "Instrument Serif Italic"},
            "title": {"enabled": True, "preset": "bar", "duration": 4, "size": 62},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": True, "color": "#FFC933"},
        },
    },
    "podcast-quote-glow": {
        "label": "Podcast · Quote glow", "niche": "podcast", "badge": "Cerita & insight",
        "desc": "Caption tenang dengan glow, satu kata kunci serif miring. Untuk cerita, insight, dan kutipan panjang.",
        "settings": {
            "content_profile": "podcast", "duration_preset": "40-60", "layout": "portrait", "smart_crop": True, "cut_silence": False,
            "caption": {"preset": "quote-glow", "style": "keyword", "box": False, "effect": "glow", "glow_color": "#C6FF3D",
                        "font": "Barlow Condensed", "size": 90, "color": "#FFFFFF", "highlight": "#C6FF3D", "uppercase": False,
                        "words_per_line": 4, "max_chars": 26, "y_pct": 64, "animation": "none", "accent_font": "Instrument Serif Italic"},
            "title": {"enabled": True, "role": "hook", "preset": "duo", "duration": 3, "size": 68, "accent": "#3DE0A0", "glow": "#C6FF3D", "y_pct": 12},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False},
        },
    },
    "tech-review": {
        "label": "Review / Tech Review", "niche": "tech_review", "badge": "Production", "status": "Production",
        "desc": "Satu caption dengan penekanan biru terkendali. Hook opsional tiga detik, produk tetap terlihat.",
        "settings": {
            "content_profile": "tech_review", "duration_preset": "25-40", "layout": "portrait", "smart_crop": True,
            "cut_silence": True, "caption_layers": 1,
            "caption": {"enabled": True, "role": "spoken-caption", "preset": "tech", "style": "keyword", "box": False,
                        "effect": "none", "font": "Barlow Condensed", "size": 84, "color": "#F8FAFC",
                        "highlight": "#38BDF8", "uppercase": False, "words_per_line": 5, "max_chars": 32,
                        "safe_area": 0.15, "y_pct": 74, "animation": "none"},
            "title": {"enabled": False, "role": "hook", "preset": "clean", "duration": 3, "size": 56, "y_pct": 12},
            "product_label": {"enabled": False, "role": "source-callout"},
            "decoration": {"mode": "none", "max_active": 1}, "emoji": {"enabled": False}, "progress_bar": {"enabled": False},
        },
    },
    "ml-hype": {
        "label": "Mobile Legends · Hype kuning", "niche": "mobile_legends", "badge": "Gaming",
        "desc": "Facecam terdeteksi otomatis → split; tanpa facecam → gameplay utuh + caption di bawah. Box kuning teks hitam (font Anton, kata kunci Bangers): paling kontras di peta hijau dan tidak bentrok dengan warna tim merah/biru.",
        "settings": {
            "content_profile": "mobile_legends", "duration_preset": "15-25", "layout": "split", "cut_silence": False,
            "split": {"auto": True, "face_ratio": 0.38},
            "caption": {"preset": "gaming", "style": "keyword", "box": True, "effect": "none", "font": "Anton", "size": 128,
                        "color": "#FFFFFF", "highlight": "#FFD60A", "uppercase": True, "words_per_line": 3, "max_chars": 20,
                        "y_pct": 40, "animation": "pop", "accent_font": "Bangers"},
            "title": {"enabled": True, "preset": "outline", "duration": 3, "size": 112},
            "emoji": {"enabled": True, "size": 0.9}, "progress_bar": {"enabled": True, "color": "#FFD60A"},
        },
    },
    "ml-neon": {
        "label": "Mobile Legends · Neon pink", "niche": "mobile_legends", "badge": "Gaming alternatif",
        "desc": "Varian mencolok untuk montage/funny moment: box magenta. Kontras baik di peta hijau; pakai bila channel-mu identik warna neon.",
        "settings": {
            "content_profile": "mobile_legends", "duration_preset": "15-25", "layout": "split", "cut_silence": False,
            "split": {"auto": True, "face_ratio": 0.38},
            "caption": {"preset": "gaming-neon", "style": "keyword", "box": True, "effect": "glow", "glow_color": "#FF2BD6",
                        "font": "Anton", "size": 128, "color": "#FFFFFF", "highlight": "#FF2BD6", "uppercase": True,
                        "words_per_line": 3, "max_chars": 20, "y_pct": 40, "animation": "pop", "accent_font": "Bangers"},
            "title": {"enabled": True, "preset": "neon", "duration": 3, "size": 112},
            "emoji": {"enabled": True, "size": 0.9}, "progress_bar": {"enabled": True, "color": "#FF2BD6"},
        },
    },
    "edukasi-wbw": {
        "label": "Educational / Explainer", "niche": "educational", "badge": "Beta", "status": "Beta",
        "desc": "Satu kata satu penekanan di tengah layar. Tempo cepat untuk tips, fakta, dan tutorial singkat.",
        "settings": {
            "content_profile": "educational", "duration_preset": "25-40", "layout": "portrait", "smart_crop": True, "cut_silence": True,
            "caption": {"preset": "wbw", "style": "wbw", "box": False, "effect": "glow", "glow_color": "#000000", "font": "Anton",
                        "size": 110, "color": "#FFFFFF", "highlight": "#FFE14D", "uppercase": True, "words_per_line": 1,
                        "y_pct": 55, "animation": "pop"},
            "title": {"enabled": True, "preset": "outline", "duration": 4, "size": 64},
            "emoji": {"enabled": True, "size": 1.0}, "progress_bar": {"enabled": True, "color": "#FFE14D"},
        },
    },
    "clipping-campaign": {
        "label": "Campaign clipping", "niche": "podcast", "badge": "Cuan per view",
        "desc": "Bersih tanpa judul tambahan, watermark akunmu, durasi aman 15–40 dtk. Cek brief campaign (hashtag, tag, disclosure) sebelum posting.",
        "settings": {
            "content_profile": "auto", "duration_preset": "auto", "layout": "portrait", "smart_crop": True, "cut_silence": True,
            "caption": {"preset": "campaign", "style": "clean", "box": True, "effect": "none", "font": "Barlow Condensed", "size": 90,
                        "color": "#FFFFFF", "highlight": "#2563FF", "uppercase": False, "words_per_line": 3, "max_chars": 22,
                        "y_pct": 62, "animation": "pop"},
            "title": {"enabled": False, "preset": "clean"},
            "watermark": {"enabled": True, "text": "@akunkamu", "position": "c", "opacity": 0.35},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False}, "cta": {"enabled": False},
        },
    },
}

def _box_punch_profile(profile: str, emoji_budget: int, priority: str) -> dict:
    base = RECIPES["box-punch"]
    return {**base, "niche": profile, "tier": "primary", "badge": "Rekomendasi",
            "label": f"Box Punch V2 · {'Podcast' if profile == 'podcast' else 'Review'}",
            "recommended_for": [profile] + (["interview"] if profile == "podcast" else ["review"]),
            "desc": ("Box Punch V2 + Emoji cerdas hemat (maks 1 aktif), tetap menjauhi wajah." if profile == "podcast"
                     else "Box Punch V2 + Emoji cerdas; area produk diprioritaskan bebas dekorasi."),
            "settings": {**base["settings"], "content_profile": profile,
                         "decoration": {"mode": "smart_emoji", "provenance": "keyword", "max_active": 1,
                                        "budget": emoji_budget, "priority": priority},
                         "emoji": {"enabled": True, "size": 0.9, "provenance": "keyword", "max_count": emoji_budget}}}


RECIPES["box-punch-podcast"] = _box_punch_profile("podcast", 3, "face")
RECIPES["box-punch-review"] = _box_punch_profile("tech_review", 5, "product")

AUTO = {"id": "auto", "label": "Auto", "niche": "auto", "badge": "Production", "status": "Production",
        "desc": "Klasifikasi mode dengan confidence dan alasan. Confidence rendah selalu memakai Clean Large tanpa dekorasi."}

# Gaming tidak berubah; profil tak dikenal / confidence rendah jatuh ke Clean Large.
PROFILE_DEFAULT = {"podcast": "box-punch-podcast", "interview": "box-punch-podcast",
                   "tech_review": "box-punch-review", "review": "box-punch-review",
                   "educational": "recommended", "gaming": "ml-hype", "mobile_legends": "ml-hype"}
FALLBACK = "recommended"


def default_for(profile: str | None) -> str:
    return PROFILE_DEFAULT.get(profile or "auto", FALLBACK)


def public() -> dict:
    return {"auto": {**AUTO, "settings": {}}, **{k: {**v, "id": k} for k, v in RECIPES.items()}}
