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
    ("gaming-neon", "Gaming Neon", "Hiburan", "Ulasan game dan budaya digital dengan aksen neon hijau.", "split", "#0b0620", "#39ff88", "#f2fff7", "Tahoma", "Ritme cepat, fokus pada mekanik dan momen kunci; jangan memakai klaim performa tanpa sumber."),
    ("misteri-malam", "Misteri Malam", "Dokumenter", "Kisah misteri dengan nuansa malam biru-ungu dan poster besar.", "poster", "#0b1020", "#818cf8", "#eef2ff", "Georgia", "Bangun suasana dari fakta yang ada; bedakan teori dari bukti dan jangan menyajikan spekulasi sebagai kepastian."),
    ("sains-lab", "Sains Lab", "Edukasi", "Penjelasan sains dan eksperimen dengan palet biru laboratorium.", "split", "#0b1b2e", "#60a5fa", "#eff6ff", "Verdana", "Jelaskan hipotesis, cara kerja dan batas bukti; satu konsep per scene."),
    ("finansial-biru", "Finansial Biru", "Bisnis", "Literasi keuangan yang tenang, biru korporat dan headline tegas.", "headline", "#0a1a33", "#38bdf8", "#f0f9ff", "Arial", "Gunakan angka hanya dari sumber, sebut asumsi, hindari janji imbal hasil."),
    ("startup-pitch", "Startup Pitch", "Bisnis", "Ringkasan produk dan strategi dengan latar terang dan tipografi bersih.", "center", "#f8fafc", "#7c3aed", "#0f172a", "Verdana", "Masalah, solusi, bukti; satu pesan per scene tanpa klaim pasar yang tidak bersumber."),
    ("kajian-teduh", "Kajian Teduh", "Religi", "Kisah dan pelajaran dengan palet hijau teduh dan emas lembut.", "center", "#0f2a24", "#e5c07b", "#fdf8ec", "Georgia", "Gunakan bahasa santun, rujuk sumber yang jelas, jangan menafsirkan teks suci tanpa rujukan; hindari visual makhluk bernyawa yang sensitif."),
    ("peta-sejarah", "Peta Sejarah", "Dokumenter", "Sejarah dan geopolitik dengan nuansa peta tua hijau zaitun.", "headline", "#1d2a22", "#d6c27a", "#f7f3e3", "Georgia", "Susun kronologi dan lokasi, sebut sumber, bedakan fakta dari interpretasi."),
    ("olahraga-energi", "Olahraga Energi", "Olahraga", "Ulasan pertandingan dan atlet dengan aksen oranye bertenaga.", "poster", "#1a0a0a", "#ff7a1a", "#fff4ea", "Arial", "Gunakan data pertandingan yang dapat diverifikasi; ritme cepat tanpa melebih-lebihkan hasil."),
    ("kuliner-hangat", "Kuliner Hangat", "Gaya Hidup", "Cerita makanan dan resep dengan palet cokelat hangat.", "poster", "#2a1408", "#ffb454", "#fff6ea", "Georgia", "Jelaskan bahan, langkah dan alasannya; tidak menjanjikan manfaat kesehatan."),
    ("travel-senja", "Travel Senja", "Gaya Hidup", "Cerita perjalanan dengan gradasi senja merah muda dan ungu.", "split", "#1a1430", "#ff8fab", "#fff1f5", "Verdana", "Sebut lokasi dan konteks nyata; jangan mengklaim pengalaman pribadi yang tidak ada."),
    ("hukum-formal", "Hukum & Kebijakan", "Edukasi", "Penjelasan hukum dan kebijakan publik yang formal dan netral.", "headline", "#121826", "#cbd5e1", "#ffffff", "Georgia", "Rujuk pasal dan sumber resmi, hindari opini hukum personal, tandai yang masih perlu verifikasi."),
    ("keluarga-hangat", "Keluarga Hangat", "Edukasi", "Parenting dan keluarga dengan latar krem dan aksen oranye lembut.", "center", "#fff7ed", "#ea580c", "#3b2a1a", "Verdana", "Bahasa suportif, hindari menghakimi, rujuk sumber untuk saran kesehatan atau psikologi."),
]
LAYOUTS = frozenset({"headline", "split", "poster", "center"})
EFFECTS = {
    "cyber-news": "technical", "investigasi-noir": "cinematic",
    "tech-future": "technical", "medis-fakta": "calm",
    "sejarah-arsip": "cinematic", "ekonomi-gold": "kinetic",
    "kelas-cerah": "calm", "motivasi-rose": "cinematic",
    "news-alert": "urgent", "minimal-ink": "minimal",
    "nature-story": "calm", "creator-pop": "kinetic",
    "gaming-neon": "kinetic", "misteri-malam": "cinematic",
    "sains-lab": "technical", "finansial-biru": "calm",
    "startup-pitch": "minimal", "kajian-teduh": "calm",
    "peta-sejarah": "cinematic", "olahraga-energi": "urgent",
    "kuliner-hangat": "calm", "travel-senja": "cinematic",
    "hukum-formal": "minimal", "keluarga-hangat": "calm",
}
EFFECT_MODES = frozenset({"technical", "cinematic", "kinetic", "calm", "urgent", "minimal"})

TEMPLATES = {
    slug: {
        "id": slug,
        "name": name,
        "category": category,
        "description": description,
        "engine": "remotion",
        "layout": layout,
        "effect": EFFECTS[slug],
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


def recommend(topic: str) -> dict:
    """Rule-based, reproducible suggestion. Never claims to infer the content of a video."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Judul video wajib diisi")
    t = " " + topic.casefold() + " "
    groups = (
        (("cyber", "siber", "phishing", "ransomware", "hack", "keamanan", "security"), "cyber-news"),
        (("surah", "ayat", "nabi", "kisah islami", "al-qur", "alquran", "doa "), "kajian-teduh"),
        (("game", "gaming", "esports"), "gaming-neon"),
        (("misteri", "kasus", "kriminal", "hilang"), "misteri-malam"),
        (("sepak bola", "olahraga", "atlet", "pertandingan", "liga"), "olahraga-energi"),
        (("resep", "kuliner", "makanan", "masakan"), "kuliner-hangat"),
        (("wisata", "travel", "liburan", "perjalanan"), "travel-senja"),
        (("hukum", "undang-undang", "pasal", "kebijakan"), "hukum-formal"),
        (("parenting", "anak", "keluarga"), "keluarga-hangat"),
        (("sains", "eksperimen", "fisika", "kimia"), "sains-lab"),
        (("startup", "pitch", "produk baru"), "startup-pitch"),
        (("ai ", "artificial intelligence", "teknologi", "software", "startup", "teknik"), "tech-future"),
        (("sejarah", "kerajaan", "perang dunia", "abad ", "heritage"), "sejarah-arsip"),
        (("medis", "kesehatan", "dokter", "penyakit", "sains tubuh"), "medis-fakta"),
        (("bisnis", "ekonomi", "saham", "uang", "keuangan", "investasi"), "ekonomi-gold"),
        (("berita", "breaking", "headline", "terbaru", "news"), "news-alert"),
        (("motivasi", "inspirasi", "semangat", "kisah hidup"), "motivasi-rose"),
        (("belajar", "kelas", "tips", "tutorial", "panduan", "cara "), "kelas-cerah"),
        (("alam", "hewan", "lingkungan", "hutan", "laut", "satwa"), "nature-story"),
    )
    for words, slug in groups:
        if any(word in t for word in words):
            return get(slug)
    return get("creator-pop")
