from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_drafter


class VideoDrafterTest(unittest.TestCase):
    def test_options_are_opuscar_only(self):
        opts = video_drafter.options()
        self.assertEqual([item["id"] for item in opts["engines"]], ["opuscar"])
        self.assertEqual(opts["defaultEngine"], "opuscar")
        self.assertNotIn("hyperframes", str(opts).lower())
        self.assertGreater(len(opts["durations"]), 1)

    def test_explicit_timecodes_and_fields_are_preserved(self):
        scenes = video_drafter.parse_explicit_scenes("00:00-00:07 Narasi: Pembuka asli\nVisual: Kota pagi\nTeks layar: Mulai\nSFX: whoosh\n\n00:07-00:20 Narasi: Isi asli\nVisual: Grafik data")
        self.assertEqual(len(scenes), 2)
        self.assertEqual((scenes[0]["start"], scenes[0]["end"]), (0, 7))
        self.assertEqual(scenes[0]["narration"], "Pembuka asli")
        self.assertEqual(scenes[0]["soundCue"], "whoosh")
        self.assertEqual(scenes[1]["end"], 20)

    def test_fallback_without_timecode_is_proportional(self):
        plan = video_drafter.normalize_scene_plan({}, "Kopi", "Pendek. Kalimat kedua jauh lebih panjang untuk menjelaskan proses seduh kopi.", 30)
        self.assertEqual(len(plan["scenes"]), 2)
        self.assertEqual(plan["scenes"][0]["start"], 0)
        self.assertEqual(plan["scenes"][-1]["end"], 30)
        self.assertGreater(plan["scenes"][1]["duration"], plan["scenes"][0]["duration"])

    def test_llm_scene_count_remains_dynamic(self):
        source = {"scenes": [{"narration": f"Bagian {index}", "type": "story"} for index in range(7)]}
        plan = video_drafter.normalize_scene_plan(source, "Dinamis", "", 70)
        self.assertEqual(len(plan["scenes"]), 7)
        composition = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["16:9"])
        self.assertEqual(composition.count('<section class="scene'), 7)
        self.assertIn('data-duration="70"', composition)

    def test_narration_subtitle_and_sound_mapping(self):
        plan = video_drafter.normalize_scene_plan({}, "Tes", "0-5 Narasi: Halo dunia\nTeks layar: HALO\nSFX: bell", 60)
        manifest = video_drafter.audio_manifest(plan)
        self.assertEqual(manifest["voice"][0]["text"], "Halo dunia")
        self.assertEqual(manifest["subtitles"][0]["end"], 5)
        self.assertEqual(manifest["soundCues"][0], {"at": 0, "cue": "bell"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitles.srt"
            video_drafter.write_subtitles(path, plan)
            self.assertIn("00:00:05,000", path.read_text(encoding="utf-8"))

    def test_visual_grammar_matches_scene_type(self):
        plan = {"topic": "Jenis", "duration": 10, "scenes": [{"id": "scene-1", "start": 0, "end": 10, "duration": 10, "narration": "Data 80%", "visual": "grafik", "onScreenText": "80%", "soundCue": "", "type": "data"}]}
        result = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["9:16"])
        self.assertIn('class="grammar data"', result)

    def test_procedural_audio_uses_scene_sound_cues(self):
        plan = video_drafter.normalize_scene_plan({}, "Audio", "0-1 Narasi: Halo\nSFX: bell", 1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bed.wav"
            video_drafter._write_procedural_audio(output, plan, sample_rate=8000)
            self.assertGreater(output.stat().st_size, 8000)

    def test_start_job_forces_opuscar_but_keeps_valid_duration(self):
        with patch.object(video_drafter.threading, "Thread"):
            result = video_drafter.start_job({"topic": "Tes", "engine": "hyperframes", "duration": 30})
        job = video_drafter.job_status(result["jobId"])
        self.assertEqual(job["engine"], "opuscar")
        self.assertEqual(job["duration"], 30)


if __name__ == "__main__":
    unittest.main()
