"""Alat kualitas transkrip per klip: filler, kata low-confidence, pratinjau potong jeda, ekspor subtitle.

Ide dari dawn-cut (filler & low-confidence review), SubtitleEdit/tscaps (ekspor SRT/VTT/SBV/ASS/TXT) dan
remotion-captions-kit (pagination). Implementasi sendiri, tanpa dependensi baru. Semua hasil hanya SARAN:
tidak ada kata yang dihapus otomatis.
"""
from __future__ import annotations

import re

# Hesitasi murni; pencocokan persis (bukan substring) agar kata normal tidak ikut terhapus.
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "eh", "ehh", "ehm", "em", "emm", "hmm", "hm", "mm", "mmm", "anu", "anuu"}
LOW_CONFIDENCE = 0.55
_BARE = re.compile(r"^\W+|\W+$", re.UNICODE)


def bare(word: str) -> str:
    return _BARE.sub("", str(word)).casefold()


def clip_words_with_p(transcript_words: list[dict], clip: dict) -> list[dict]:
    """Kata klip (waktu relatif) lengkap dengan probabilitas `p`.

    Bila klip punya kata hasil edit (`clip["words"]`), pakai itu dan lengkapi `p` dari transkrip (cocok per waktu mulai).
    """
    start, end = float(clip["start"]), float(clip["end"])
    by_start = {round(float(w["s"]) - start, 2): w.get("p") for w in transcript_words}
    if clip.get("words"):
        return [{**w, "p": w.get("p", by_start.get(round(float(w["s"]), 2)))} for w in clip["words"]]
    return [{"w": w["w"], "s": round(float(w["s"]) - start, 3), "e": round(float(w["e"]) - start, 3), "p": w.get("p")}
            for w in transcript_words if float(w["s"]) >= start - 0.05 and float(w["e"]) <= end + 0.3]


def analyze(words: list[dict], low: float = LOW_CONFIDENCE) -> dict:
    """Saran perbaikan: filler, kata berulang (gagap), dan kata dengan keyakinan ASR rendah."""
    fillers, repeats, uncertain = [], [], []
    for i, w in enumerate(words):
        b = bare(w["w"])
        item = {"i": i, "w": w["w"], "s": w["s"], "e": w["e"]}
        if b in FILLERS:
            fillers.append(item)
        elif i and b and b == bare(words[i - 1]["w"]) and len(b) > 1 and (w["s"] - words[i - 1]["e"]) < 0.6:
            repeats.append(item)
        p = w.get("p")
        if p is not None and p < low and b and b not in FILLERS:
            uncertain.append({**item, "p": round(float(p), 2)})
    total = len(words)
    return {"words": total, "fillers": fillers, "repeats": repeats, "low_confidence": uncertain,
            "filler_pct": round(100 * len(fillers) / total, 1) if total else 0.0,
            "uncertain_pct": round(100 * len(uncertain) / total, 1) if total else 0.0,
            "has_probability": any(w.get("p") is not None for w in words),
            "note": "Saran saja. Tidak ada kata yang dihapus otomatis."}


def drop_indices(words: list[dict], indices: set[int]) -> list[dict]:
    return [w for i, w in enumerate(words) if i not in indices]


def silence_preview(words: list[dict], duration: float, gap: float = 0.55, pad: float = 0.12) -> dict:
    """Pratinjau 'potong jeda hening': rentang yang dipertahankan dan waktu yang dihemat (tanpa render)."""
    from .render import cut_plan

    duration = max(float(duration), 0.5)
    plan = cut_plan(words, duration, gap, pad) if words else [(0.0, duration)]
    kept = sum(b - a for a, b in plan)
    cuts, prev = [], 0.0
    for a, b in plan:
        if a - prev > 0.05:
            cuts.append({"s": round(prev, 2), "e": round(a, 2), "dur": round(a - prev, 2)})
        prev = b
    if duration - prev > 0.05:
        cuts.append({"s": round(prev, 2), "e": round(duration, 2), "dur": round(duration - prev, 2)})
    return {"original": round(duration, 2), "result": round(kept, 2), "saved": round(duration - kept, 2),
            "saved_pct": round(100 * (duration - kept) / duration, 1), "segments": len(plan), "cuts": cuts,
            "gap": gap, "pad": pad}


def timeline_words(words: list[dict], duration: float, cfg: dict) -> list[dict]:
    """Waktu kata mengikuti timeline hasil render (setelah jeda dipotong bila fiturnya aktif)."""
    if not cfg.get("cut_silence") or not words:
        return words
    from .render import cut_plan, remap

    plan = cut_plan(words, max(float(duration), 0.5), float(cfg.get("silence_gap", 0.55)))
    return [{**w, "s": round(remap(w["s"], plan), 3), "e": round(remap(w["e"], plan), 3)} for w in words]


# ---------------------------------------------------------------- ekspor subtitle
FORMATS = {"srt": "application/x-subrip", "vtt": "text/vtt", "sbv": "text/plain", "ass": "text/x-ssa", "txt": "text/plain"}


def _t(sec: float, sep: str = ",", hours: bool = True) -> str:
    ms = int(round(max(sec, 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}" if hours else f"{h}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _cs(sec: float) -> str:
    cs = int(round(max(sec, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _lines(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    from .caption_workspace import segment

    return [g for g in segment(words, max(1, max_words), max_chars) if g]


def export_subtitles(words: list[dict], fmt: str = "srt", per_line: int = 5, max_chars: int = 36,
                     word_timing: bool = False, title: str = "ClipperCuan") -> str:
    """SRT / VTT / SBV / ASS / TXT. `word_timing` menambah karaoke (ASS \\k) atau tag waktu per kata (VTT)."""
    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise ValueError(f"Format tidak dikenal: {fmt}. Pilihan: {', '.join(FORMATS)}")
    groups = _lines(words, per_line, max_chars)
    spans = []
    for i, g in enumerate(groups):
        end = float(g[-1]["e"]) + 0.15
        if i + 1 < len(groups):
            end = min(end, float(groups[i + 1][0]["s"]))
        spans.append((float(g[0]["s"]), max(end, float(g[0]["s"]) + 0.1)))
    text = lambda g: " ".join(str(w["w"]) for w in g)  # noqa: E731
    if fmt == "txt":
        return "\n".join(text(g) for g in groups) + "\n"
    if fmt == "srt":
        return "\n".join(f"{i + 1}\n{_t(a)} --> {_t(b)}\n{text(g)}\n" for i, (g, (a, b)) in enumerate(zip(groups, spans)))
    if fmt == "sbv":
        return "\n".join(f"{_t(a, '.', False)},{_t(b, '.', False)}\n{text(g)}\n" for g, (a, b) in zip(groups, spans))
    if fmt == "vtt":
        out = ["WEBVTT\n"]
        for i, (g, (a, b)) in enumerate(zip(groups, spans)):
            body = " ".join(f"<{_t(float(w['s']), '.')}>{w['w']}" if word_timing and j else str(w["w"]) for j, w in enumerate(g))
            out.append(f"{i + 1}\n{_t(a, '.')} --> {_t(b, '.')}\n{body}\n")
        return "\n".join(out)
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
            "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,0,2,60,60,260,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    rows = []
    for g, (a, b) in zip(groups, spans):
        if word_timing:
            body = " ".join(f"{{\\k{max(1, int(round((float(w['e']) - float(w['s'])) * 100)))}}}{w['w']}" for w in g)
        else:
            body = text(g)
        rows.append(f"Dialogue: 0,{_cs(a)},{_cs(b)},Default,,0,0,0,,{body}".replace("\n", " "))
    return head + "\n".join(rows) + "\n"
