"""Cari momen menarik dari transkrip + energi audio, lalu buat judul pembuka.

Skor tiap kandidat (0..100) gabungan dari:
  hook      kalimat pembuka berisi pertanyaan / angka / kata pemicu
  keywords  kata emosional & pemicu penasaran di sepanjang klip
  energy    rata-rata + puncak energi audio
  pace      kecepatan bicara (kata per detik) — terlalu lambat = membosankan
  complete  klip berakhir di akhir kalimat
"""
from __future__ import annotations

import re

import numpy as np

HOOK_WORDS = {
    # Indonesia
    "rahasia", "jangan", "ternyata", "kenapa", "gimana", "bagaimana", "cara", "trik", "tips", "kesalahan",
    "penting", "wajib", "harus", "pertama", "terbesar", "terbaik", "terburuk", "jujur", "sebenarnya",
    "pernah",
    "uang", "duit", "cuan", "gaji", "juta", "miliar", "gratis", "bahaya", "gila", "parah", "serius",
    "kaget", "viral", "stop", "berhenti", "hidup", "mati", "sukses", "gagal", "bisnis", "rezeki",
    # English
    "secret", "never", "always", "why", "how", "mistake", "biggest", "best", "worst", "money", "truth",
    "actually", "crazy", "insane", "important", "stop", "nobody", "everyone", "million", "free",
}
# Kata ganti & negasi umum: ada di hampir setiap kalimat, jadi bobotnya kecil (hanya penguat, bukan pemicu).
WEAK_HOOK_WORDS = {"nggak", "gak", "enggak", "tidak", "semua", "orang", "kamu", "lo", "lu", "gue", "aku", "you"}
EMO_WORDS = {
    "wow", "anjir", "astaga", "gokil", "mantap", "keren", "sedih", "senang", "marah", "takut", "cinta",
    "benci", "bangga", "malu", "nangis", "ketawa", "lucu", "amazing", "love", "hate", "scared", "funny",
}
_TOKEN = re.compile(r"[\w']+", re.UNICODE)
FILLERS = {"um", "uh", "eh", "anu", "hmm", "kayak", "literally", "basically"}
DURATION_PRESETS = {"15-25": (15.0, 25.0), "25-40": (25.0, 40.0), "40-60": (40.0, 60.0)}


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", "?", "!", "…", "。", "？", "！"))


def _hook_score(text: str) -> float:
    toks = _tokens(text)[:18]
    s = 0.0
    if "?" in text:
        s += 0.35
    if any(t.isdigit() for t in toks):
        s += 0.2
    s += min(sum(t in HOOK_WORDS for t in toks) * 0.15 + sum(t in WEAK_HOOK_WORDS for t in toks) * 0.03, 0.6)
    return min(s, 1.0)


def duration_range(preset: str, tr: dict | None = None) -> tuple[float, float, str]:
    """Pilih rentang Auto dari kepadatan ujaran dan struktur ide, tetap pada batas kalimat."""
    if preset in DURATION_PRESETS:
        a, b = DURATION_PRESETS[preset]
        return a, b, f"Preset {preset} detik"
    segs = (tr or {}).get("segments", [])
    words = (tr or {}).get("words", [])
    span = (segs[-1]["e"] - segs[0]["s"]) if segs else 0
    pace = len(words) / max(span, 1)
    avg_idea = span / max(len(segs), 1)
    if pace >= 2.8 and avg_idea <= 5:
        return 15.0, 25.0, "Ujaran padat dan ide cepat mencapai payoff"
    if pace >= 1.8 or avg_idea <= 8:
        return 25.0, 40.0, "Ide butuh konteks sedang sebelum payoff"
    return 40.0, 60.0, "Ujaran lebih tenang; rentang panjang menjaga ide tetap utuh"


def _is_punctuated(segs: list[dict]) -> bool:
    """Subtitle YouTube otomatis tidak punya tanda baca; untuk itu jeda bicara dipakai sebagai batas kalimat."""
    return bool(segs) and sum(_ends_sentence(x["text"]) for x in segs) / len(segs) >= 0.2


def _clean_end(segs: list[dict], words: list[dict], j: int, punctuated: bool) -> bool:
    if punctuated:
        return _ends_sentence(segs[j]["text"])
    if j + 1 >= len(segs):
        return True
    return segs[j + 1]["s"] - segs[j]["e"] >= 0.45


def _candidate_breakdown(first: str, full: str, last: str, pace: float, energy_s: float, conf: float,
                         clean_end: bool | None = None, visual_s: float | None = None) -> dict:
    toks = _tokens(full)
    hook = round(_hook_score(first) * 100)
    novelty = min(100, round(len(set(toks)) / max(len(toks), 1) * 150))
    emotional = min(100, round(sum(t in EMO_WORDS for t in toks) * 28 + energy_s * 45))
    clarity = max(0, 100 - (25 if re.match(r"^(dan|tapi|jadi|terus|ini|itu)\b", first.strip(), re.I) else 0))
    payoff = 100 if (_ends_sentence(last) if clean_end is None else clean_end) else 25
    quotability = min(100, round(_hook_score(full) * 70 + (20 if len(toks) <= 35 else 0)))
    visual = min(100, round(energy_s * 75 + 15) if visual_s is None else round(100 * (0.7 * visual_s + 0.3 * energy_s)))
    density = max(0, min(100, round(100 - abs(pace - 2.5) * 28)))
    ending = payoff
    penalties = {
        "slow_intro": 20 if pace < 1.1 else 0,
        "repetition": max(0, round((1 - len(set(toks)) / max(len(toks), 1) - .35) * 100)),
        "filler": min(25, sum(t in FILLERS for t in toks) * 5),
        "context_dependency": 20 if clarity < 100 else 0,
        "incomplete": 30 if payoff < 100 else 0,
    }
    return {"hook": hook, "novelty": novelty, "emotional_shift": emotional, "clarity": clarity,
            "payoff": payoff, "quotability": quotability, "visual_action": visual,
            "information_density": density, "clean_ending": ending, "penalties": penalties,
            "transcript_confidence": round(conf * 100)}


def readiness(breakdown: dict) -> tuple[int, list[str]]:
    keys = ("hook", "novelty", "emotional_shift", "clarity", "payoff", "quotability", "visual_action", "information_density", "clean_ending")
    score = sum(float(breakdown.get(k, 0)) for k in keys) / len(keys)
    score -= sum(float(v) for v in breakdown.get("penalties", {}).values()) * .35
    warnings = []
    if breakdown.get("transcript_confidence", 100) < 70: warnings.append("Kualitas transkrip rendah")
    if breakdown.get("hook", 0) < 45: warnings.append("Hook 0-3 detik lemah")
    if breakdown.get("clean_ending", 0) < 70: warnings.append("Akhir klip belum bersih")
    return max(0, min(100, round(score))), warnings


def score_candidates(tr: dict, energy: np.ndarray, min_sec: float = 20, max_sec: float = 60, hop: float = 0.5,
                     visual: np.ndarray | None = None) -> list[dict]:
    """Semua jendela kandidat (dari batas kalimat) beserta skor lokal, urut terbaik."""
    segs, words = tr["segments"], tr["words"]
    punctuated = _is_punctuated(segs)
    cands = []
    for i, first in enumerate(segs):
        text_parts = []
        for j in range(i, len(segs)):
            text_parts.append(segs[j]["text"])
            start, end = first["s"], segs[j]["e"]
            length = end - start
            if length > max_sec:
                break
            if length < min_sec:
                continue
            full = " ".join(text_parts)
            nwords = sum(len(segs[k]["words"]) for k in range(i, j + 1))
            pace = nwords / max(length, 1)
            e0, e1 = int(start / hop), max(int(end / hop), int(start / hop) + 1)
            en = energy[e0:e1] if energy.size else np.zeros(1)
            if en.size == 0:
                en = np.zeros(1)
            energy_s = float(en.mean() * 0.6 + np.percentile(en, 90) * 0.4)
            visual_s = None
            if visual is not None and visual.size:
                vw = visual[e0:e1]
                visual_s = float(vw.mean() * 0.5 + np.percentile(vw, 90) * 0.5) if vw.size else None
            conf = float(np.mean([words[k]["p"] for k in range(first["words"][0], segs[j]["words"][-1] + 1)]))
            ideal = 1 - min(abs(length - (min_sec + max_sec) / 2) / max_sec, 1) * 0.3
            breakdown = _candidate_breakdown(first["text"], full, segs[j]["text"], pace, energy_s, conf,
                                             _clean_end(segs, words, j, punctuated), visual_s)
            ready, warnings = readiness(breakdown)
            score = ready / 100 * ideal
            cands.append({"s": start, "e": end, "seg0": i, "seg1": j, "score": score, "text": full,
                          "breakdown": breakdown, "readiness": ready, "warnings": warnings,
                          "confidence": round(conf, 3)})
    if not cands and segs:  # video lebih pendek dari min_sec
        cands = [{"s": segs[0]["s"], "e": segs[-1]["e"], "seg0": 0, "seg1": len(segs) - 1, "score": 0.5,
                  "text": " ".join(x["text"] for x in segs)}]
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands


def non_overlapping(cands: list[dict], count: int, max_overlap: float = 0.15, taken: list[dict] | None = None) -> list[dict]:
    chosen = list(taken or [])
    for c in cands:
        if len(chosen) >= count:
            break
        if all(min(c["e"], o["e"]) - max(c["s"], o["s"]) < max_overlap * (c["e"] - c["s"]) for o in chosen):
            chosen.append(c)
    return chosen


def explain(c: dict, segs: list[dict]) -> str:
    """Alasan singkat (bahasa manusia) kenapa kandidat ini dipilih skor lokal."""
    first = segs[c["seg0"]]["text"]
    toks = _tokens(c["text"])
    why = []
    if "?" in first:
        why.append("dibuka dengan pertanyaan")
    elif any(t.isdigit() for t in _tokens(first)):
        why.append("dibuka dengan angka")
    elif _hook_score(first) >= 0.3:
        why.append("kalimat pembuka kuat")
    kw = sorted({t for t in toks if t in HOOK_WORDS and len(t) > 3}, key=toks.index)[:3]
    if kw:
        why.append("kata pemicu: " + ", ".join(kw))
    if any(t in EMO_WORDS for t in toks):
        why.append("ada emosi")
    if _ends_sentence(segs[c["seg1"]]["text"]):
        why.append("berakhir di kalimat utuh")
    return " · ".join(why) or "alur bicara padat"


STOP = set("""yang dan di ke dari ini itu untuk dengan pada adalah juga tidak bisa akan ada kita kami saya aku kamu
dia mereka atau tapi jadi karena kalau sudah belum lebih sangat banyak satu dua tiga seperti dalam oleh agar
supaya bahwa saja lagi ya nah oke apa siapa kapan mana mau harus nya pun kenapa mengapa gimana bagaimana
pertama kedua ketiga terakhir semua orang nggak enggak gak tidak pernah sekarang nanti tadi hari waktu cara
benar benar sebenarnya ternyata jangan coba sama setiap selalu masih bukan hanya bisa banget kalian
the a an and or of to in on for is are was were be it this that with as at by you your i we they he she not
but so if just very more why how what when never always""".split())


def title_options(text: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out = []
    for s in sentences[:8]:
        t = make_title([s], 7)
        if t and t not in out: out.append(t)
    return (out + [make_title([text], 6), "Inti yang perlu kamu tahu"])[0:3]


def post_kit(text: str, title: str, language: str | None = None) -> dict:
    """Caption posting + hashtag tanpa AI: kata kunci terbanyak + tag umum short video."""
    toks = [t for t in _tokens(text) if len(t) > 3 and t not in STOP and not t.isdigit()]
    freq: dict[str, int] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1 + (0.5 if len(t) > 6 else 0)  # kata panjang cenderung kata kunci topik
    keys = [k for k, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:5]]
    base = ["#shortvideo"] if language != "id" else ["#videopendek"]
    tags = [f"#{k}" for k in keys[:4]] + base
    cta = "Bagian mana yang paling relevan buatmu?" if language in (None, "id", "ms") else "Which part is most useful to you?"
    head = title.strip()
    if head and head[-1] not in ".?!…":
        head += "…"
    context = "Ringkasan praktis dari pembahasan ini." if language in (None, "id", "ms") else "Practical takeaway from this discussion."
    return {"caption": f"{head}\n\n{context} {cta}".strip(), "hashtags": tags,
            "title_options": title_options(text), "hashtag_groups": {"topic": tags[:-1], "format": tags[-1:]}}


def to_moment(c: dict, segs: list[dict], duration: float, score: int, title: str | None = None, **extra) -> dict:
    extra.setdefault("reason", explain(c, segs))
    return {
        "start": round(max(c["s"] - 0.15, 0), 2), "end": round(min(c["e"] + 0.35, duration), 2), "score": int(score),
        "readiness": int(c.get("readiness", score)), "breakdown": c.get("breakdown", {}),
        "warnings": c.get("warnings", []), "confidence": c.get("confidence", .5),
        "title": title or make_title([segs[k]["text"] for k in range(c["seg0"], c["seg1"] + 1)]),
        "text": c["text"], **extra,
    }


def find_moments(tr: dict, energy: np.ndarray, duration: float, count: int = 6,
                 min_sec: float = 20, max_sec: float = 60, hop: float = 0.5, visual: np.ndarray | None = None) -> list[dict]:
    if not tr["segments"]:
        return _fallback(duration, count, min_sec, max_sec)
    chosen = non_overlapping(score_candidates(tr, energy, min_sec, max_sec, hop, visual), count)
    top = max(c["score"] for c in chosen) or 1
    out = [to_moment(c, tr["segments"], duration, round(60 + 39 * c["score"] / top)) for c in chosen]
    out.sort(key=lambda m: m["score"], reverse=True)
    return out


def _fallback(duration, count, min_sec, max_sec):
    """Tanpa ucapan (mis. gameplay tanpa suara): bagi rata."""
    length = min(max_sec, max(min_sec, duration / max(count, 1)))
    out, t = [], 0.0
    while t + min_sec <= duration and len(out) < count:
        out.append({"start": round(t, 2), "end": round(min(t + length, duration), 2), "score": 60, "title": f"Momen {len(out) + 1}", "text": ""})
        t += length
    return out or [{"start": 0, "end": round(duration, 2), "score": 60, "title": "Momen 1", "text": ""}]


def make_title(sentences: list[str], max_words: int = 7) -> str:
    """Pilih kalimat paling 'menjual' lalu ringkas jadi judul pembuka."""
    best, best_s = sentences[0] if sentences else "", -1.0
    for i, s in enumerate(sentences[:6]):
        sc = _hook_score(s) + (0.15 if i == 0 else 0) - max(len(_tokens(s)) - 14, 0) * 0.02
        if sc > best_s:
            best, best_s = s, sc
    best = re.sub(r"^(jadi|nah|oke|ok|terus|dan|ya|so|and|well|um|eh)[,\s]+", "", best.strip(), flags=re.I)
    words = best.split()
    title = " ".join(words[:max_words]).strip(" ,.;:")
    if len(words) > max_words and not title.endswith("?"):
        title += "…"
    return title[:1].upper() + title[1:] if title else "Momen terbaik"
