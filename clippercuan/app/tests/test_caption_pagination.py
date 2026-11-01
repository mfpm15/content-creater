"""Pagination caption: pola dari remotion-captions-kit (singkatan, pecah di koma, kata yatim) tanpa dependensi baru."""
from clipper import caption_workspace as cw


def words(text: str, step: float = .3, gap_after: dict | None = None) -> list[dict]:
    gap_after, out, t = gap_after or {}, [], 0.0
    for i, w in enumerate(text.split()):
        out.append({"w": w, "s": round(t, 3), "e": round(t + step * .9, 3), "p": .9})
        t += step + gap_after.get(i, 0)
    return out


def texts(chunks):
    return [" ".join(w["w"] for w in c) for c in chunks]


def test_abbreviation_does_not_end_sentence():
    out = texts(cw.segment(words("Kata Dr. Budi soal vs. Android itu benar"), max_words=12, max_chars=80))
    assert out == ["Kata Dr. Budi soal vs. Android itu benar"]


def test_real_sentence_end_still_breaks():
    out = texts(cw.segment(words("Ini selesai. Lalu mulai lagi"), max_words=12, max_chars=80))
    assert out == ["Ini selesai.", "Lalu mulai lagi"]


def test_forced_break_moves_to_nearest_comma():
    out = texts(cw.segment(words("kami kemas mobil, kunci pintu dan pergi jauh sekali"), max_words=7, max_chars=80))
    assert out[0] == "kami kemas mobil,"
    assert " ".join(out) == "kami kemas mobil, kunci pintu dan pergi jauh sekali"


def test_orphan_word_is_evened_out_after_forced_break():
    out = texts(cw.segment(words("ini tempat kamu mulai"), max_words=4, max_chars=80))
    assert all(len(c.split()) >= 2 for c in out)


def test_pause_boundary_is_never_crossed_and_no_word_is_lost():
    ws = words("satu dua tiga empat lima", gap_after={1: 1.0})
    chunks = cw.segment(ws, max_words=9, max_chars=80)
    assert texts(chunks)[0].endswith("dua")           # jeda nyata tetap memisahkan
    assert [w["w"] for c in chunks for w in c] == [w["w"] for w in ws]
