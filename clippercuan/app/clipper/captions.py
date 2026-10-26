"""Generator subtitle ASS: caption per kata (box/word-by-word/karaoke/clean), judul, watermark teks."""
from __future__ import annotations

from .caption_workspace import segment, timing_mode

FONT_PRESETS = {
    # nama tampilan → (nama font, bold)
    "Montserrat ExtraBold": ("Montserrat ExtraBold", 0),
    "Anton": ("Anton", 0),
    "Bebas Neue": ("Bebas Neue", 0),
    "Poppins Black": ("Poppins Black", 0),
    "Bangers": ("Bangers", 0),
    "Arial Black": ("Arial Black", 0),
    "Impact": ("Impact", 0),
    "Georgia Italic": ("Georgia", 1),
    "Barlow Condensed": ("Barlow Condensed ExtraBold", 0),
    "Instrument Serif": ("Instrument Serif", 0),
    "Instrument Serif Italic": ("Instrument Serif", 1),
    "Pinyon Script": ("Pinyon Script", 0),
}
# Font aksen untuk gaya "Subtract & font": kata kunci memakai font berbeda (serif miring/script).
ACCENT_FONTS = ("Instrument Serif Italic", "Pinyon Script", "Georgia Italic", "Bangers", "Anton")


def _ass_color(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = f"{int(round((1 - alpha) * 255)):02X}"
    return f"&H{a}{b}{g}{r}".upper()


def _text_on(hex_color: str) -> str:
    """Warna teks yang terbaca di atas kotak berwarna (hitam untuk kotak terang)."""
    h = (hex_color or "#000000").lstrip("#")[:6].ljust(6, "0")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "&H00000000&" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6 else "&H00FFFFFF&"


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _word_tags(w: dict) -> str:
    """Gaya per kata dari editor: {"color": "#hex", "scale": 1.3}."""
    st = w.get("style") or {}
    tags = ""
    if st.get("font"):
        name, ital = FONT_PRESETS.get(st["font"], (st["font"], 0))
        tags += rf"\fn{name}\i{ital}"
    if st.get("color"):
        tags += r"\c" + _ass_color(st["color"])
    sc = st.get("scale")
    if sc and abs(float(sc) - 1) > 0.01:
        v = int(float(sc) * 100)
        tags += rf"\fscx{v}\fscy{v}"
    return tags


def _keyword_index(line: list[dict]) -> int | None:
    """Satu kata paling 'berbobot' per baris (pemicu/emosi > angka > kata panjang); None bila tak ada."""
    from .highlights import EMO_WORDS, GAME_WORDS, HOOK_WORDS, STOP

    best, best_s = None, 0.0
    for i, w in enumerate(line):
        t = "".join(ch for ch in w["w"].lower() if ch.isalnum())
        if not t:
            continue
        sc = 3.0 if t in HOOK_WORDS or t in EMO_WORDS or t in GAME_WORDS else 2.0 if any(ch.isdigit() for ch in t) else (
            1.0 + len(t) / 20 if len(t) >= 6 and t not in STOP else 0.0)
        if (w.get("style") or {}).get("emphasis"):
            sc = 10.0
        if sc > best_s:
            best, best_s = i, sc
    return best


def _title_lines(title: str) -> tuple[str, str]:
    """Pecah judul jadi baris pengantar + baris punchline (preset Duo)."""
    t = title.strip()
    if "?" in t[:-1]:
        a, b = t.split("?", 1)
        if b.strip():
            return a.strip() + "?", b.strip()
    words = t.split()
    if len(words) < 3:
        return "", t
    k = max(1, round(len(words) / 3))
    return " ".join(words[:-k]), " ".join(words[-k:])


def chunk_words(words: list[dict], per_line: int, max_chars: int = 24) -> list[list[dict]]:
    """Segmentasi frasa deterministik dengan pelindung entitas dan orphan prevention."""
    return segment(words, max(1, per_line), max_chars)


def build_ass(words: list[dict], title: str, cfg: dict, size: tuple[int, int], duration: float) -> str:
    W, H = size
    cap, ttl, wm = cfg["caption"], cfg["title"], cfg["watermark"]
    font, italic = FONT_PRESETS.get(cap["font"], (cap["font"], 0))
    scale = W / 1080
    fs = int(cap["size"] * scale)
    align = {"bottom": 2, "middle": 5, "top": 8}[cap.get("position", "bottom")]
    safe = max(.08, min(.28, float(cap.get("safe_area", .12))))
    margin_v = int(H * (max(.18, safe) if align == 2 else safe if align == 8 else 0))
    white, hl = _ass_color(cap["color"]), _ass_color(cap["highlight"])
    tfs = int(ttl["size"] * scale)

    styles = [
        f"Style: Cap,{font},{fs},{white},{white},&H00000000,&H64000000,0,{italic},0,0,100,100,0,0,1,{max(int(5 * scale), 2)},{int(2 * scale)},{align},60,60,{margin_v},1",
        f"Style: CapBox,{font},{fs},&HFF000000,&HFF000000,{hl},&HFF000000,0,{italic},0,0,100,100,0,0,3,{max(int(10 * scale), 4)},0,{align},60,60,{margin_v},1",
        f"Style: TitleBar,{font},{tfs},&H00000000,&H00000000,{hl},&H00000000,0,0,0,0,100,100,0,0,3,{int(18 * scale)},0,8,90,90,{int(H * 0.10)},1",
        f"Style: TitleOutline,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{max(int(9 * scale), 4)},{max(int(4 * scale), 2)},8,90,90,{int(H * 0.10)},1",
        f"Style: TitleNeon,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00FF7B8B,&H00FF7B8B,0,0,0,0,100,100,0,0,1,{max(int(4 * scale), 2)},0,8,90,90,{int(H * 0.10)},1",
        f"Style: TitleClean,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,{max(int(3 * scale), 2)},{int(4 * scale)},8,90,90,{int(H * 0.10)},1",
        f"Style: CTA,{font},{int(64 * scale)},&H00000000,&H00000000,{hl},&H64000000,0,0,0,0,100,100,0,0,3,{int(20 * scale)},0,5,80,80,0,1",
        f"Style: Mark,Arial Black,{int(wm['size'] * scale)},{_ass_color('#FFFFFF', wm['opacity'])},&H00FFFFFF,{_ass_color('#000000', wm['opacity'] * 0.6)},&H00000000,0,0,0,0,100,100,0,0,1,{max(int(2 * scale), 1)},0,2,40,40,40,1",
    ]
    ev: list[str] = []

    def add(layer, start, end, style, text):
        if end > start:
            ev.append(f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    # ---- caption
    if cap["enabled"] and words:
        style = cap["style"]
        word_timing = timing_mode(words) == "word"
        box_on = (style == "box" or bool(cap.get("box"))) and word_timing  # kotak mengikuti kata aktif
        if style in {"karaoke", "box"} and not word_timing:
            style = "clean"  # phrase timing tidak boleh membuat highlight kata palsu
        up = (lambda s: s.upper()) if cap.get("uppercase") else (lambda s: s)
        pop = cap.get("animation") == "pop"
        glow = cap.get("effect") == "glow"
        glow_col = _ass_color(cap.get("glow_color") or cap["highlight"])
        pos = ""
        if cap.get("y_pct") not in (None, ""):
            y = int(H * max(.08, min(.92, float(cap["y_pct"]) / 100)))
            pos = rf"\an5\pos({W // 2},{y})"
        acc_font, acc_italic = FONT_PRESETS.get(cap.get("accent_font") or "Instrument Serif Italic", ("Instrument Serif", 1))
        keyword = style == "keyword"
        box_text = _text_on(cap["highlight"])

        def head(extra: str = "") -> str:
            return "{" + pos + extra + "}" if (pos or extra) else ""

        def glow_layer(start, end, text_plain):
            if glow:  # lapisan bawah: outline kabur berwarna = efek glow
                add(0, start, end, "Cap", head(rf"\bord{max(int(6 * scale), 3)}\blur{max(int(6 * scale), 3)}\3c{glow_col}\3a&H50&\1a&HFF&\shad0") + text_plain)

        if style == "wbw":
            for i, w in enumerate(words):
                end = words[i + 1]["s"] if i + 1 < len(words) and words[i + 1]["s"] - w["e"] < 0.4 else w["e"]
                if i + 1 < len(words):
                    end = min(end, words[i + 1]["s"])
                anim = r"\fscx92\fscy92\t(0,120,\fscx104\fscy104)\t(120,220,\fscx100\fscy100)" if pop else ""
                t = _esc(up(w["w"]))
                glow_layer(w["s"], end, t)
                add(1, w["s"], end, "Cap", head(anim + r"\c" + hl) + t)
        else:
            lines = chunk_words(words, int(cap.get("words_per_line", 3)), int(cap.get("max_chars", 24)))
            for li, line in enumerate(lines):
                l_end = line[-1]["e"] + 0.15
                if li + 1 < len(lines):  # jangan sampai bertumpuk dengan baris berikutnya
                    l_end = min(l_end, lines[li + 1][0]["s"])
                kw = _keyword_index(line) if keyword else None

                def word_text(j: int, x: dict, active: bool) -> str:
                    t = _esc(up(x["w"]))
                    own = _word_tags(x)
                    tags = own
                    if j == kw:  # kata kunci: font aksen, miring, warna sorotan, sedikit lebih besar
                        tags += rf"\fn{acc_font}\i{acc_italic}\c{hl}\fscx118\fscy118"
                    if active and box_on:
                        tags += r"\c" + box_text + r"\bord0\shad0"
                    elif active and style == "karaoke":
                        tags += r"\c" + hl
                    return ("{" + tags + "}" + t + r"{\r}") if tags else t

                per_word = box_on or style == "karaoke"
                if not per_word:
                    plain = " ".join(_esc(up(x["w"])) for x in line)
                    glow_layer(line[0]["s"], l_end, plain)
                    anim = r"\fad(80,0)" if pop else ""
                    add(1, line[0]["s"], l_end, "Cap", head(anim) + " ".join(word_text(j, x, False) for j, x in enumerate(line)))
                    continue
                for k, w in enumerate(line):
                    s0 = w["s"] if k else line[0]["s"]
                    e0 = line[k + 1]["s"] if k + 1 < len(line) else l_end
                    grow = r"\t(0,120,\fscx104\fscy104)\t(120,220,\fscx100\fscy100)" if pop else ""
                    if box_on:  # lapis bawah: kotak solid hanya di kata aktif
                        box_parts = []
                        for j, x in enumerate(line):
                            t = _esc(up(x["w"]))
                            kwt = rf"\fn{acc_font}\i{acc_italic}\fscx118\fscy118" if j == kw else ""
                            vis = r"\1a&HFF&\3a&H00&\4a&HFF&" + grow if j == k else r"\1a&HFF&\3a&HFF&\4a&HFF&"
                            box_parts.append("{" + _word_tags(x) + kwt + vis + "}" + t)
                        add(0, s0, e0, "CapBox", head() + " ".join(box_parts))
                    else:
                        glow_layer(s0, e0, " ".join(_esc(up(x["w"])) for x in line))
                    add(1, s0, e0, "Cap", head() + " ".join(word_text(j, x, j == k) for j, x in enumerate(line)))

    # ---- judul pembuka
    if ttl["enabled"] and title.strip():
        preset = ttl.get("preset", "bar")
        t_end = duration if not ttl.get("duration") else min(float(ttl["duration"]), duration)
        if preset == "duo":  # baris pengantar putih miring + punchline besar berwarna, keduanya bercahaya
            first, second = _title_lines(title)
            acc = _ass_color(ttl.get("accent") or "#3DE0A0")
            gl = _ass_color(ttl.get("glow") or "#C6FF3D")
            y1 = int(H * 0.12)
            sharp = rf"\shad0\bord{max(int(3 * scale), 2)}\3c&H00101010&"
            glow = rf"\1a&HFF&\shad0\bord{max(int(8 * scale), 4)}\blur{max(int(8 * scale), 4)}\3a&H40&"
            if first:
                base = rf"\an8\pos({W // 2},{y1})\fad(200,0)\i1\fscx115\fscy115"
                add(2, 0, t_end, "TitleClean", "{" + base + glow + rf"\3c{gl}" + "}" + _esc(first))
                add(3, 0, t_end, "TitleClean", "{" + base + sharp + "}" + _esc(first))
            lines1 = 1 + len(first) // 24 if first else 0
            y2 = y1 + int(tfs * 1.2 * lines1)
            base = rf"\an8\pos({W // 2},{y2})\fad(250,0)\i1\fscx150\fscy150"
            add(2, 0, t_end, "TitleClean", "{" + base + glow + rf"\3c{acc}" + "}" + _esc(second))
            add(3, 0, t_end, "TitleClean", "{" + base + sharp + rf"\c{acc}" + "}" + _esc(second))
            t_end = -1  # sudah ditambahkan
        style = {"bar": "TitleBar", "outline": "TitleOutline", "neon": "TitleNeon", "clean": "TitleClean"}.get(preset, "TitleBar")
        fx = r"{\fad(200,0)\frz-2}" if preset == "bar" else r"{\fad(200,0)\blur3}" if preset == "neon" else r"{\fad(200,0)}"
        add(2, 0, t_end, style, fx + _esc(title.upper() if preset != "clean" else title))  # t_end<0 → dilewati add()
        if preset == "neon":  # lapisan teks tajam di atas glow
            add(3, 0, t_end, style, r"{\fad(200,0)\bord0}" + _esc(title.upper()))

    # ---- ajakan (CTA) di akhir klip
    cta = cfg.get("cta", {})
    if cta.get("enabled") and cta.get("text", "").strip() and duration > 2:
        c_start = max(duration - float(cta.get("duration", 3)), duration * 0.5)
        y = int(H * 0.42)
        add(5, c_start, duration, "CTA", r"{\an5\pos(" + f"{W // 2},{y}" + r")\fad(250,0)\fscx60\fscy60\t(0,220,\fscx108\fscy108)\t(220,350,\fscx100\fscy100)}"
            + _esc(cta["text"].strip()))

    # ---- watermark teks
    if wm["enabled"] and wm.get("text") and not wm.get("image"):
        an = {"tl": 7, "tr": 9, "bl": 1, "br": 3, "c": 5}.get(wm["position"], 3)
        mx, my = int(40 * scale), int(H * 0.05)
        pos = {7: (mx, my), 9: (W - mx, my), 1: (mx, H - my), 3: (W - mx, H - my), 5: (W // 2, H // 2)}[an]
        add(4, 0, duration, "Mark", r"{\an" + str(an) + r"\pos(" + f"{pos[0]},{pos[1]}" + ")}" + _esc(wm["text"]))

    head = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\nYCbCr Matrix: TV.709\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
        "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return head + "\n".join(ev) + "\n"


def _srt_ts(t: float) -> str:
    t = max(t, 0)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list[dict], per_line: int = 3) -> str:
    """Subtitle .srt standar (untuk diunggah terpisah ke YouTube/TikTok)."""
    lines = chunk_words(words, max(per_line, 4), 32)
    out = []
    for i, line in enumerate(lines):
        end = line[-1]["e"] + 0.15
        if i + 1 < len(lines):
            end = min(end, lines[i + 1][0]["s"])
        out.append(f"{i + 1}\n{_srt_ts(line[0]['s'])} --> {_srt_ts(end)}\n{' '.join(w['w'] for w in line)}\n")
    return "\n".join(out)
