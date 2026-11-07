"""True voice-synchronized captions, no synthesized word-timing guesses."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
import asyncio

import video_drafter as vd
import remotion_adapter
import word_timing
import speech_worker


class WordTimingTests(unittest.TestCase):
    def plan(self):
        return vd.normalize_scene_plan({
            "scenes":[{"start":0,"end":2,"narration":"Halo dunia","onScreenText":"Halo dunia"}],
            "captionStyle":"highlight","fps":30,
        },"Halo dunia","",2)

    def _write(self, root, rows):
        voice=root/"voice";voice.mkdir(exist_ok=True)
        f=voice/"scene-1.words.jsonl"
        f.write_text("\n".join(json.dumps(item,ensure_ascii=False) for item in rows), "utf-8")
        return f

    def test_provider_word_boundaries_roundtrip_into_remotion_without_touching_approved_plan(self):
        plan=self.plan()
        before=copy.deepcopy(plan)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self._write(root,[
                {"type":"WordBoundary","offset":0,"duration":5000000,"text":"Halo"},
                {"type":"WordBoundary","offset":6000000,"duration":5000000,"text":"dunia"},
            ])
            enriched,report=word_timing.enrich(plan,root)
        self.assertEqual(plan,before)
        self.assertEqual(len(report["alignedScenes"]),1)
        self.assertEqual(enriched["scenes"][0]["wordCueSource"],"edge_tts")
        self.assertAlmostEqual(enriched["scenes"][0]["wordCues"][1]["start"],.6)
        props,renderer_report=remotion_adapter.manifest(enriched,{"width":320,"height":568})
        self.assertEqual(props["captionStyle"],"highlight")
        self.assertEqual(props["captions"][0]["wordFrames"][0]["text"],"Halo")
        self.assertEqual(renderer_report["caption_timing"][0]["method"],"edge_tts_word_boundaries_rounded_to_frames")

    def test_missing_and_incomplete_provider_data_does_not_fake_alignment(self):
        plan=self.plan()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            actual,report=word_timing.enrich(plan,root)
            self.assertFalse(report["aligned"])
            self.assertNotIn("wordCues",actual["scenes"][0])
            self._write(root,[{"type":"WordBoundary","offset":0,"duration":1000000,"text":"Halo"}])
            actual,report=word_timing.enrich(plan,root)
            self.assertFalse(report["aligned"])
            self.assertEqual(actual["scenes"][0]["narration"],"Halo dunia")
            self.assertNotIn("wordCues",actual["scenes"][0])

    def test_out_of_slot_or_bad_metadata_is_rejected(self):
        plan=self.plan()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for rows in (
                [{"type":"WordBoundary","offset":999999999,"duration":1000000,"text":"Halo"}],
                [{"type":"WordBoundary","offset":"0","duration":10000,"text":"Halo"}],
            ):
                self._write(root,rows)
                result,report=word_timing.enrich(plan,root)
                self.assertFalse(report["aligned"])
                self.assertTrue(report["warnings"])
                self.assertNotIn("wordCues",result["scenes"][0])

    def test_original_user_cues_take_precedence_over_provider(self):
        plan=self.plan()
        plan["scenes"][0]["wordCues"]=[
            {"word":"Halo","start":0,"end":.5},{"word":"dunia","start":.5,"end":1}
        ]
        with tempfile.TemporaryDirectory() as folder:
            result,report=word_timing.enrich(plan,Path(folder))
        self.assertEqual(result["scenes"][0]["wordCues"],plan["scenes"][0]["wordCues"])
        self.assertFalse(report["aligned"])

    def test_worker_requests_word_boundaries_in_same_audio_synthesis(self):
        arguments=[]
        class Communicate:
            def __init__(self,*args,**kwargs):
                arguments.append(kwargs)
            async def save(self,audio,metadata):
                Path(audio).write_bytes(b"mp3-sample")
                Path(metadata).write_text('{"type":"WordBoundary","offset":0,"duration":3000000,"text":"Halo"}\n',"utf-8")
        def fake_ffmpeg(cmd,**kwargs):
            Path(cmd[-1]).write_bytes(b"wav")
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as folder,\
             patch.dict(sys.modules,{"edge_tts":SimpleNamespace(Communicate=Communicate)}),\
             patch.object(speech_worker.subprocess,"run",side_effect=fake_ffmpeg):
            asyncio.run(speech_worker.synthesize([{"id":"scene-1","text":"Halo","voice":"id-ID-ArdiNeural","rate":"+0%"}],Path(folder)))
            self.assertTrue((Path(folder)/"scene-1.wav").exists())
            self.assertTrue((Path(folder)/"scene-1.words.jsonl").exists())
            self.assertFalse((Path(folder)/"scene-1.part.words.jsonl").exists())
        self.assertEqual(arguments[0]["boundary"],"WordBoundary")


if __name__ == "__main__":
    unittest.main()
