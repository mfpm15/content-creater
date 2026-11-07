"""Curated first-party faceless templates for the Remotion Editorial adapter.

Presets are design directions, not stock footage or generic text-to-video claims.
Store a concrete snapshot per job so later catalogue changes cannot silently
change previously approved output.
"""
from __future__ import annotations

from copy import deepcopy

# All colours are validated via creative_profile.brand before use.
# Layouts correspond to actual Remotion composition variants.
_ROWS = [
    ("cyber-news", "Berita Siber", "Teknologi", "Berita keamanan digital dengan headline kuat dan sinyal peringatan.", "headline", "#071424", "#14d8f5", "#ffffff", "Arial", "Faktual, serius, cepat, buktikan klaim dan hindari sensasionalisme."),
    ("investigasi-noir", "Investigasi Noir", "Dokumenter", "Kisah investigasi, atmosfer gelap dan fokus pada dokumen.", "poster", "#120e19", "#fb7185", "#fff5f5", "Georgia", "Bangun rasa penasaran, paparkan bukti berurutan, hindari ilustrasi palsu."),
    ("tech-future", "Tech Future", "Teknologi", "Explainer teknologi dengan aksen elektrik dan depth.", "split", "#0a1030", "#a78bfa", "#f5f5ff", "Arial", "Tampilkan perangkat, mekanisme dan manfaat nyata dengan penjelasan bertahap."),
    ("medis-fakta", "Medis & Fakta", "Edukasi", "Penjelasan sains kesehatan yang tenang dan mudah dibaca.", "split", "#06222a", "#42dfc1", "#e8fffa", "Verdana", "Gunakan bahasa hati-hati, utamakan penjelasan dan sumber terpercaya."),
    ("sejarah-arsip", "Sejarah Arsip", "Dokumenter", "Cerita sejarah dengan nuansa arsip kertas dan tipografi serif.", "headline", "#261d16", "#d7a867", "#fff7e8", "Georgia", "Susun kronologi dan sumber; bedakan fakta dari rekonstruksi visual."),
    ("ekonomi-gold", "Ekonomi Gold", "Bisnis", "Ringkasan ekonomi dengan hierarki metrik tanpa angka rekaan.", "poster", "#1b160c", "#f2bc57", "#fffcf0", "Georgia", "Hanya tampilkan angka dari sumber; jelaskan konteks dan keterbatasan data."),
    ("kelas-cerah", "Kelas Cerah", "Edukasi", "Explainer ringan dengan latar cerah dan teks jelas.", "split", "#f3f6ff", "#315fd4", "#152443", "Verdana", "Pecah konsep sulit menjadi tiga langkah sederhana dan contoh konkret."),
    ("motivasi-rose", "Motivasi Rose", "Storytelling", "Kisah inspiratif dengan fokus pesan dan emosi.", "center", "#240f28", "#fb83b7", "#fff6fd", "Georgia", "Tulis narasi hangat, hindari repetisi kata dan janji yang tidak realistis."),
    ("news-alert", "Breaking News", "Berita", "Headline cepat dengan aksen merah untuk informasi terkini.", "headline", "#230d17", "#ff665e", "#fff8f5", "Arial", "Cantumkan waktu dan sumber, jangan membuat peristiwa atau kutipan fiktif."),
    ("minimal-ink", "Minimal Ink", "Minimalis", "Desain hitam putih fokus tipografi dan ilustrasi relevan.", "center", "#101114", "#e6e9ef", "#ffffff", "Arial", "Kurangi dekorasi; utamakan satu pesan utama per scene."),
    ("nature-story", "Nature Story", "Dokumenter", "Dokumenter alam bernuansa hijau dan tenang.", "poster", "#10241f", "#8de4a5", "#effff3", "Georgia", "Jelaskan subjek dan hubungan sebab akibat, gunakan visual alam yang relevan."),
    ("creator-pop", "Creator Pop", "Sosial Media", "Konten fakta cepat dengan judul mencolok dan ritme dinamis.", "split", "#24122c", "#f5a2ff", "#fff7ff", "Tahoma", "Hook ringkas, ritme bervariasi, CTA tidak memaksa, hindari format identik setiap video."),
]
LAYOUTS = frozenset({"headline", "split", "poster", "center"})
TEMPLATES = {
    slug: {
        "id": slug,
        "name": name,
        "category": category,
        "description": description,
        "engine": "remotion",
        "layout": layout,
        "direction": direction,
        "brand": {
            "name": name,
            "background": background,
            "accent": accent,
            "text": text,
            "font": font,
            "wordmark": "",
        },
    }
    for slug, name, category, description, layout, background, accent, text, font, direction in _ROWS
}


def get(template_id: str) -> dict:
    if not isinstance(template_id, str) or template_id not in TEMPLATES:
        raise ValueError("Template video tidak dikenal; muat ulang katalog")
    return deepcopy(TEMPLATES[template_id])


def catalogue() -> list[dict]:
    return [get(template_id) for template_id in TEMPLATES]
