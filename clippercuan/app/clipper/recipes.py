"""Resep gaya viral siap pakai: satu klik mengatur durasi, format, caption, judul, dan efek.

Disusun dari pola yang terlihat pada klip short-form populer (box highlight per kata, kata kunci dengan font aksen,
judul hook dua baris, caption huruf campuran di tengah-bawah frame) dan disesuaikan dengan niche ClipperCuan.
Ini titik awal yang masuk akal, bukan jaminan viral: uji A/B dengan data unggahan sendiri.
"""
from __future__ import annotations

RECIPES: dict[str, dict] = {
    "recommended": {
        "label": "Rekomendasi · Clean Pro", "niche": "auto", "badge": "Default aman",
        "desc": "Satu layer subtitle utama yang bersih, maksimal dua baris, tanpa efek dekoratif otomatis.",
        "settings": {
            "content_profile": "auto", "duration_preset": "auto", "layout": "portrait", "smart_crop": True,
            "cut_silence": False, "caption_layers": 1, "source_has_burned_captions": "unknown",
            "caption": {"enabled": True, "role": "spoken-caption", "preset": "clean-pro", "style": "clean",
                        "box": False, "effect": "none", "font": "Barlow Condensed", "size": 64,
                        "outline": 3, "shadow": 0, "color": "#FFFFFF", "highlight": "#FFD166",
                        "uppercase": False, "words_per_line": 4, "max_chars": 28,
                        "safe_area": 0.18, "y_pct": 78, "animation": "none"},
            "title": {"enabled": False, "role": "hook", "preset": "clean", "duration": 3, "size": 58, "y_pct": 12},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False}, "cta": {"enabled": False},
        },
    },
    "clean-focus": {
        "label": "Clean Focus · Keyword", "niche": "auto", "badge": "Menarik & aman",
        "desc": "Baseline bersih dengan satu kata penting berwarna kuning dan pembesaran halus. Tanpa karaoke, glow, box aktif, atau pergantian font.",
        "settings": {
            "content_profile": "auto", "duration_preset": "auto", "layout": "portrait", "smart_crop": True,
            "cut_silence": False, "caption_layers": 1, "source_has_burned_captions": "unknown",
            "caption": {"enabled": True, "role": "spoken-caption", "preset": "clean-focus", "style": "keyword",
                        "box": False, "effect": "none", "font": "Barlow Condensed", "size": 66,
                        "outline": 3, "shadow": 0, "color": "#FFFFFF", "highlight": "#FFD166",
                        "uppercase": False, "words_per_line": 4, "max_chars": 28,
                        "safe_area": 0.18, "y_pct": 76, "animation": "none",
                        "accent_font": "Barlow Condensed", "accent_mode": "color", "accent_scale": 108},
            "title": {"enabled": False, "role": "hook", "preset": "clean", "duration": 3, "size": 58, "y_pct": 12},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False}, "cta": {"enabled": False},
        },
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
        "label": "Review tech · Fokus biru", "niche": "tech_review", "badge": "Opt-in",
        "desc": "Satu caption dengan penekanan biru terkendali. Hook opsional tiga detik, produk tetap terlihat.",
        "settings": {
            "content_profile": "tech_review", "duration_preset": "25-40", "layout": "portrait", "smart_crop": True,
            "cut_silence": True, "caption_layers": 1,
            "caption": {"enabled": True, "role": "spoken-caption", "preset": "tech", "style": "karaoke", "box": False,
                        "effect": "none", "font": "Barlow Condensed", "size": 78, "color": "#F8FAFC",
                        "highlight": "#38BDF8", "uppercase": False, "words_per_line": 5, "max_chars": 32,
                        "safe_area": 0.15, "y_pct": 74, "animation": "none"},
            "title": {"enabled": False, "role": "hook", "preset": "clean", "duration": 3, "size": 56, "y_pct": 12},
            "emoji": {"enabled": False}, "progress_bar": {"enabled": False},
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
        "label": "Edukasi · Word by word", "niche": "podcast", "badge": "Tips & tutorial",
        "desc": "Satu kata satu penekanan di tengah layar. Tempo cepat untuk tips, fakta, dan tutorial singkat.",
        "settings": {
            "content_profile": "auto", "duration_preset": "25-40", "layout": "portrait", "smart_crop": True, "cut_silence": True,
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

AUTO = {"id": "auto", "label": "Otomatis sesuai konten", "niche": "auto", "badge": "Lanjutan",
        "desc": "Deteksi konten tetap tersedia, tetapi gaya dekoratif tidak lagi dipilih otomatis untuk podcast atau review teknologi."}

PROFILE_DEFAULT = {"podcast": "recommended", "tech_review": "recommended", "mobile_legends": "ml-hype"}


def public() -> dict:
    return {"auto": {**AUTO, "settings": {}}, **{k: {**v, "id": k} for k, v in RECIPES.items()}}
