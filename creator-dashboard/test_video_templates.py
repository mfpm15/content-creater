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
            self.assertIn(row["effect"], video_templates.EFFECT_MODES)

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
            self.assertEqual(props["effect"], "technical")
            self.assertEqual(report["templateId"], "cyber-news")
            self.assertEqual(props["brand"]["accent"], video_templates.get("cyber-news")["brand"]["accent"])
            changed = {**plan, "templateId": "news-alert"}
            with self.assertRaisesRegex(ValueError, "template tidak boleh diganti"):
                vd.update_job_plan(key, {"stage": "scene_plan", "revision": 0, "scenePlan": changed})

    def test_existing_jobs_keep_editorial_layout(self):
        plan = vd.normalize_scene_plan({
            "scenes": [{"start": 0, "end": 5, "narration": "Selamat datang", "onScreenText": "Halo"}],
        }, "Tanpa preset", "", 5)
        props, report = remotion_adapter.manifest(plan, vd.ASPECT_RATIOS["9:16"])
        self.assertEqual(props["layout"], "editorial")
        self.assertIsNone(report["templateId"])


    def test_two_templates_produce_real_different_mp4_frames_when_runtime_ready(self):
        if remotion_adapter.runtime_issues():
            self.skipTest("Requires optional Node/Remotion/FFmpeg/browser")
        frames = []
        with tempfile.TemporaryDirectory() as temp:
            for slug in ("cyber-news", "kelas-cerah"):
                preset = video_templates.get(slug)
                plan = vd.normalize_scene_plan({
                    "scenes": [{
                        "start": 0, "end": 1, "narration": "Tiga fasilitas memerlukan keamanan.",
                        "onScreenText": "Tiga fasilitas", "visualFamily": "concept",
                    }],
                    "fps": 30, "templateId": slug, "brand": preset["brand"],
                    "captionStyle": "pop" if slug == "cyber-news" else "pill",
                }, "Tiga fasilitas", "", 1)
                target = Path(temp) / slug
                target.mkdir()
                output, report = remotion_adapter.render(target, plan, {"width": 320, "height": 568})
                self.assertTrue(output.is_file() and output.stat().st_size > 1000)
                self.assertTrue(report["deterministic_repeat"])
                self.assertEqual(len(report["frames"]), 1)
                self.assertTrue(report["layout"]["dom_measurement_available"])
                frame_path = target / report["frames"][0]["file"]
                self.assertTrue(frame_path.is_file())
                frames.append(frame_path.read_bytes())
        self.assertNotEqual(frames[0], frames[1], "Templates must change actual rendered pixels")


if __name__ == "__main__":
    unittest.main()
