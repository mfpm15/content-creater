from __future__ import annotations

import json
import unittest
from pathlib import Path

import video_drafter

ROOT = Path(__file__).resolve().parent


class VideoDrafterTest(unittest.TestCase):
    def test_options(self):
        opts = video_drafter.options()
        self.assertIn("styles", opts)
        self.assertIn("aspects", opts)
        self.assertIn("durations", opts)
        self.assertGreaterEqual(len(opts["styles"]), 4)

    def test_clean_json(self):
        sample = '```json\n{"badge": "AI", "headline": "Halo Dunia"}\n```'
        cleaned = video_drafter._clean_json(sample)
        self.assertEqual(cleaned.get("badge"), "AI")
        self.assertEqual(cleaned.get("headline"), "Halo Dunia")

    def test_generate_html_composition(self):
        script_data = {
            "badge": "TEST",
            "headline": "Testing Video",
            "subline": "Subtitle test line",
            "callout": "Action Now"
        }
        style_info = video_drafter.STYLES["tech_keynote"]
        aspect_info = video_drafter.ASPECT_RATIOS["9:16"]
        html = video_drafter._generate_html_composition("Test Topic", script_data, style_info, aspect_info, 5)
        self.assertIn("data-composition-id=\"video\"", html)
        self.assertIn("Testing Video", html)
        self.assertIn("gsap.timeline", html)


if __name__ == "__main__":
    unittest.main()
