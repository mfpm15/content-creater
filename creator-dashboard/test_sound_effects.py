from array import array
from pathlib import Path
import tempfile
import unittest
import wave

import sound_effects
import speech_settings
import video_drafter as vd


class SoundEffectTests(unittest.TestCase):
    def test_effects_are_repeatable_and_silent_outside_cue_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[Path(folder)/f'{i}.wav' for i in range(2)]
            for path in paths:sound_effects.write(path,2,[{'at':.5,'cue':'whoosh'},{'at':1.2,'cue':'chime'}],8000)
            self.assertEqual(paths[0].read_bytes(),paths[1].read_bytes())
            with wave.open(str(paths[0])) as f:data=array('h',f.readframes(f.getnframes()))
            self.assertFalse(any(data[:4000]));self.assertTrue(any(data[4000:6240]))
            self.assertFalse(any(data[6240:9600]));self.assertTrue(any(data[9600:12160]))
            self.assertFalse(any(data[12160:]));self.assertLess(max(abs(n) for n in data),8000)

    def test_sfx_flag_and_silent_mode_preserve_no_music_contract(self):
        self.assertTrue(speech_settings.build()['sfx'])
        # Existing approved settings without an SFX field keep their prior silence.
        self.assertFalse(speech_settings.validate({'mode':'tts','language':'id'})['sfx'])
        for flag,mode,expected in [(True,'tts',True),(False,'tts',False),(True,'none',False)]:
            plan=vd.normalize_scene_plan({'speech':speech_settings.build('id',mode,flag),'scenes':[
                {'start':0,'end':2,'narration':'Halo','soundCue':'click'}]},'Test','',2)
            manifest=vd.audio_manifest(plan)
            self.assertFalse(manifest['music']['enabled']);self.assertEqual(bool(manifest['soundCues']),expected)
