from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("youtube_analytics", Path(__file__).with_name("youtube_analytics.py"))
assert _SPEC and _SPEC.loader
ya = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ya)


class YouTubeAnalyticsTests(unittest.TestCase):
    def test_retention_detects_cliff_and_matches_srt(self):
        body = b"Timestamp,Audience retention\n0,100\n1,96\n2,90\n3,70\n4,69\n"
        srt = "1\n00:00:02,000 --> 00:00:04,000\nPembuka terlalu lama\n"
        result = ya.analyze_retention(body, srt)
        self.assertEqual(result["summary"]["sample_count"], 5)
        self.assertTrue(any(x["kind"] == "cliff" for x in result["events"]))
        self.assertIn("Pembuka", next(x["spoken"] for x in result["events"] if x["second"] == 3))
        self.assertEqual(result["method"], "diagnostic_not_causal")

    def test_retention_rejects_bad_csv(self):
        with self.assertRaises(ValueError):
            ya.analyze_retention(b"foo,bar\na,b\n")

    def test_package_linter_flags_duplication(self):
        result = ya.lint_package("Cara Membuat Video Shorts Lebih Jelas", "Video Shorts Lebih Jelas")
        self.assertLess(result["score"], 100)
        self.assertTrue(result["metrics"]["overlap"])

    def test_hook_review_is_non_predictive(self):
        result = ya.review_hook("Kenapa 3 detik pertama menentukan video ini?")
        self.assertGreaterEqual(result["score"], 60)
        self.assertIn("not_prediction", result["method"])


if __name__ == "__main__":
    unittest.main()
