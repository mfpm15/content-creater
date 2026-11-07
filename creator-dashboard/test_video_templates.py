"""Regression coverage for the first-party faceless template catalogue."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import creative_profile
import remotion_adapter
import video_drafter as vd
import video_templates


class VideoTemplateTests(unittest.TestCase):
    def test_catalogue_is_unique_curated_and_validated(self):
        entries = video_templates.catalogue()
        self.assertGreaterEqual(len(entries), 12)
        self.assertEqual(len({entry["id"] for entry in entries}), len(entries))
        self.assertTrue({"headline", "split", "poster", "center"}.issubset({row["layout"] for row in entries}))
        for row in entries:
            self.assertEqual(row["engine"], "remotion")
            self.assertEqual(row["brand"], creative_profile.brand(row["brand"]))
            self.assertLessEqual(len(row["direction"]), 500)

    def test_unknown_template_never_creates_a_job(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(vd, "JOBS", {}), patch.object(vd, "JOB_DIR", Path(folder)):
            with patch.object(vd.threading.Thread, "start") as start:
                with self.assertRaisesRegex(ValueError, "Template video tidak dikenal"):
                    vd.start_job({"topic": "Konten", "templateId": "../../tmp", "engine": "remotion"})
                with self.assertRaisesRegex(ValueError, "Remotion"):
                    vd.start_job({"topic": "Konten", "templateId": "cyber-news", "engine": "opuscar"})
                start.assert_not_called()
            self.assertFalse(list(Path(folder).glob("*")))

    def test_template_is_carried_to_job_plan_manifest_and_variants(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(vd, "JOBS", {}), \
             patch.object(vd, "JOB_DIR", Path(folder) / "jobs"), \
             patch.object(vd, "VIDEOS_DIR", Path(folder) / "videos"), \
             patch.object(vd.threading.Thread, "start"):
            key = vd.start_job({
                "topic": "Tiga fasilitas", "script": "Tiga fasilitas membutuhkan perhatian.",
                "engine": "remotion", "templateId": "cyber-news",
                "researchMode": "provided", "duration": 15,
            })["jobId"]
            started = vd.job_status(key)
            self.assertEqual(started["templateId"], "cyber-news")
            self.assertEqual(started["brand"]["background"], video_templates.get("cyber-news")["brand"]["background"])
            vd._run_job(key)
            finished = vd.job_status(key)
            self.assertEqual(finished["status"], "awaiting_scene_plan", finished.get("error"))
            plan = finished["scenePlan"]
            self.assertEqual(plan["templateId"], "cyber-news")
            self.assertEqual(plan["brand"]["background"], video_templates.get("cyber-news")["brand"]["background"])
            props, report = remotion_adapter.manifest(plan, vd.ASPECT_RATIOS["9:16"])
            self.assertEqual(props["layout"], "headline")
            self.assertEqual(report["templateId"], "cyber-news")
            self.assertEqual(props["brand"]["accent"], video_templates.get("cyber-news")["brand"]["accent"])

    def test_existing_jobs_keep_editorial_layout(self):
        plan = vd.normalize_scene_plan({
            "scenes": [{"start": 0, "end": 5, "narration": "Selamat datang", "onScreenText": "Halo"}],
        }, "Tanpa preset", "", 5)
        props, report = remotion_adapter.manifest(plan, vd.ASPECT_RATIOS["9:16"])
        self.assertEqual(props["layout"], "editorial")
        self.assertIsNone(report["templateId"])


if __name__ == "__main__":
    unittest.main()
