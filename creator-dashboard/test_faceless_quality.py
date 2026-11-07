import unittest

import faceless_quality


def scene(index, title, *, family="concept", narration="Contoh narasi yang dapat dibaca dengan jelas.", duration=5):
    return {"id": f"scene-{index}", "start": (index - 1) * duration, "end": index * duration,
            "onScreenText": title, "visualFamily": family, "narration": narration}


class FacelessQualityTests(unittest.TestCase):
    def test_flags_repetitive_abstract_storyboards_and_disabled_narration(self):
        plan = {"scenes": [
            scene(1, "Judul sama"), scene(2, "Judul sama"), scene(3, "Ringkasan"),
            scene(4, "Ringkasan 2"), scene(5, "Ringkasan 3"),
        ], "speech": {"mode": "none"}}
        result = faceless_quality.inspect(plan)
        self.assertEqual(result["status"], "needs_review")
        codes = {item["code"] for item in result["warnings"]}
        self.assertTrue({"duplicate_headline", "abstract_overuse", "narration_disabled"} <= codes)

    def test_good_structured_storyboard_still_requires_manual_review(self):
        plan = {"scenes": [
            scene(1, "Tanggal kejadian", family="evidence"),
            scene(2, "Tiga fasilitas", family="process"),
            scene(3, "Layanan terganggu", family="signal"),
            scene(4, "Kesimpulan", family="kinetic-type"),
        ], "speech": {"mode": "tts"}}
        result = faceless_quality.inspect(plan)
        self.assertEqual(result["status"], "manual_review_required")
        self.assertEqual(result["warnings"], [])
        self.assertGreaterEqual(len(result["manualRequired"]), 3)

    def test_approved_local_images_count_as_concrete_artwork(self):
        images=[{**scene(i, f"Visual {i}"),"assetId":f"{i:032x}"} for i in range(1,6)]
        self.assertNotIn("abstract_overuse",
            {issue["code"] for issue in faceless_quality.inspect({"scenes":images})["warnings"]})

    def test_repeated_images_and_unaligned_word_highlights_are_flagged(self):
        plan={"scenes":[{**scene(1, "Pembuka"),"assetId":"1"*32},
                        {**scene(2, "Lanjutan"),"assetId":"1"*32}],
              "captionStyle":"highlight"}
        codes={item["code"] for item in faceless_quality.inspect(plan)["warnings"]}
        self.assertTrue({"reused_hero_image","word_alignment_missing"} <= codes)

    def test_dense_scene_and_music_only_are_warnings_not_censorship(self):
        plan = {"scenes": [scene(1, "Judul", narration=" ".join(["sangat"]*50), duration=1)],
                "audioMode": "music"}
        result = faceless_quality.inspect(plan)
        codes = {w["code"] for w in result["warnings"]}
        self.assertTrue({"dense_narration", "short_scene", "music_only"} <= codes)


if __name__ == "__main__":
    unittest.main()
