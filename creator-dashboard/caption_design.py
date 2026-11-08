"""Video Studio caption presentation, independent of actual speech alignment."""
STYLES = {
    "karaoke": {"id": "karaoke", "name": "Karaoke Pop", "description": "Kata aktif menyala dan membesar mengikuti suara"},
    "clean": {"id": "clean", "name": "Clean Editorial", "description": "Teks jelas dan minimal"},
    "pop": {"id": "pop", "name": "Kinetic Pop", "description": "Frasa masuk dengan pop berirama"},
    "pill": {"id": "pill", "name": "Moving Pill", "description": "Teks di kapsul warna yang bergerak"},
    "outline": {"id": "outline", "name": "Cinematic Outline", "description": "Teks sinematik dengan stroke tipis"},
    "highlight": {"id": "highlight", "name": "Word Highlight", "description": "Sorot kata jika tersedia timestamp asli"},
}
DEFAULT = "karaoke"


def validate(value: str | None) -> str:
    if value is None:
        return DEFAULT
    if not isinstance(value, str) or value not in STYLES:
        raise ValueError("Gaya caption tidak dikenal")
    return value


def options() -> list[dict]:
    return list(STYLES.values())
