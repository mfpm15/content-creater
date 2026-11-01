from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("humanizer", Path(__file__).with_name("humanizer.py"))
assert _SPEC and _SPEC.loader
hz = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hz)

NATURAL = (
    "Kami menguji tiga aplikasi kasir selama dua minggu. Hasilnya beragam. Aplikasi pertama cepat tetapi sering macet saat jaringan lemah. "
    "Yang kedua lambat, namun tidak pernah kehilangan data transaksi, bahkan ketika listrik padam di tengah shift malam. "
    "Murah? Tidak juga. Harganya dua kali lipat pesaing. Aplikasi ketiga paling nyaman dipakai kasir baru karena tombolnya besar. "
    "Satu hal mengganggu: laporan harian harus diekspor manual. Kalau toko Anda buka sampai larut, itu menyita waktu."
)
ROBOTIC = (
    "Di era digital saat ini, keamanan siber memainkan peran penting. Tidak dapat dipungkiri bahwa ancaman terus meningkat. "
    "Selain itu, organisasi perlu menerapkan kontrol yang memadai. Dengan demikian, risiko dapat ditekan secara efektif. "
    "Oleh karena itu, pelatihan karyawan menjadi hal yang krusial. Perlu dicatat bahwa kebijakan harus diperbarui. "
    "Selain itu, audit berkala dilakukan setiap tahun. Dengan demikian, kepatuhan dapat dijaga. "
    "Pada dasarnya, keamanan adalah tanggung jawab bersama. Sebagai kesimpulan, kewaspadaan adalah kunci."
)


class HumanizerTests(unittest.TestCase):
    def codes(self, text):
        return {f["code"] for f in hz.lint(text)["findings"]}

    def test_robotic_text_is_flagged_and_scores_lower(self):
        robotic, natural = hz.lint(ROBOTIC), hz.lint(NATURAL)
        self.assertLess(robotic["score"], natural["score"])
        self.assertIn("klise", self.codes(ROBOTIC))
        self.assertIn("penghubung", self.codes(ROBOTIC))
        self.assertEqual(natural["findings"], [])
        self.assertEqual(natural["score"], 100)

    def test_uniform_rhythm_and_repeated_starters(self):
        flat = " ".join("Sistem ini bekerja dengan baik sekali." for _ in range(9))
        self.assertTrue({"ritme", "awalan"} <= self.codes(flat))

    def test_not_just_x_but_y_pattern_from_real_article(self):
        # Kalimat asli dari artikel hasil 9Router (keamanan-siber-untuk-umkm-1024-170416-f2).
        real = (
            "Kerapuhan digital pada sektor UMKM bukan sekadar masalah perangkat lunak, melainkan kesenjangan struktural antara pemahaman risiko dan implementasi mitigasi. "
            "Pilar ini bukan sekadar istilah teknis, melainkan perlindungan langsung terhadap kelancaran kas. "
            "Disiplin dalam menutup celah kredensial bukan sekadar tindakan teknis, melainkan langkah tata kelola operasional mendasar. "
            "Sindikat menyasar UMKM bukan semata-mata karena jumlah aset, melainkan karena rasio efisiensi serangan."
        )
        self.assertIn("bukan-sekadar", self.codes(real))
        self.assertNotIn("bukan-sekadar", self.codes("Kami tidak hanya menguji. Hasilnya dicatat. Laporan selesai."))

    def test_short_or_empty_text_never_crashes_or_flags_statistics(self):
        for text in ("", None, "Satu kalimat saja.", "Dua kalimat. Hanya dua."):
            result = hz.lint(text)
            self.assertEqual(result["findings"], [])
            self.assertEqual(result["score"], 100)

    def test_citations_and_bold_are_ignored(self):
        self.assertEqual(hz.lint("Fakta penting **tebal** [1] dan [2, 3] tercatat.")["findings"], [])

    def test_score_is_bounded_and_method_is_honest(self):
        result = hz.lint(" ".join(["Di era digital saat ini, tidak dapat dipungkiri bahwa pada dasarnya hal ini menunjukkan bahwa."] * 12))
        self.assertTrue(0 <= result["score"] <= 100)
        self.assertIn("not_detector", result["method"])

    def test_article_text_takes_body_blocks_only(self):
        text = hz.article_text([
            {"type": "h2", "text": "Judul"}, {"type": "p", "text": "Isi."}, {"type": "bullets", "items": ["a", "b"]},
            {"type": "callout", "title": "T", "text": "Catatan."}, {"type": "table", "header": ["X"], "rows": [["Y"]]},
            {"type": "image", "id": "g", "caption": "C"}])
        self.assertIn("Isi.", text)
        self.assertIn("Catatan.", text)
        self.assertNotIn("Judul", text)
        self.assertNotIn("Y", text.replace("Isi.", ""))


if __name__ == "__main__":
    unittest.main()
