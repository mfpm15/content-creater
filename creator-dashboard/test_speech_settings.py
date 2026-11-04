import copy
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch

import speech_settings as speech
import video_drafter as vd
import video_preproduction as pp


class SpeechTests(unittest.TestCase):
    def test_defaults_languages_and_paid_provider_rejection(self):
        self.assertEqual(speech.build()['voice'],'id-ID-ArdiNeural')
        self.assertEqual(speech.build('en')['voice'],'en-US-GuyNeural')
        for value in ({'provider':'openai'},{'music':True},{'language':'zh'},{'voice':'arbitrary'},{'rate':'+40%'}):
            with self.assertRaises(ValueError):speech.validate(value)

    def test_job_preserves_speech_across_edit_and_variant(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',Path(temp)),patch.object(vd.threading.Thread,'start'):
            key=vd.start_job({'topic':'Test','script':'Kalimat asli.','engine':'remotion','researchMode':'provided','speechLanguage':'en'})['jobId']
            vd._run_job(key);job=vd.job_status(key)
            self.assertEqual(job['scenePlan']['speech']['language'],'en')
            self.assertEqual(job['scenePlan']['scenes'][0]['narration'],'Kalimat asli.')
            manifest=vd.audio_manifest(job['scenePlan']);self.assertFalse(manifest['music']['enabled']);self.assertEqual(manifest['soundCues'],[])
            raw=copy.deepcopy(job['scenePlan']);raw['speech']={'language':'id','mode':'none'}
            edited=vd.update_job_plan(key,{'stage':'scene_plan','revision':0,'scenePlan':raw})
            self.assertEqual(edited['scenePlan']['audioMode'],'none')
            self.assertEqual(edited['speech']['mode'],'none')
            with patch.object(vd,'get_video',return_value={'engine':'remotion','scenePlan':edited['scenePlan']}):
                variant=vd.create_aspect_jobs('fixture',['1:1'])[0]
                self.assertEqual(variant['speech'],edited['speech'])

    def test_generated_narration_uses_selected_language(self):
        prompt=pp.script_prompt('Test','',15,'en')
        self.assertIn('English',prompt)
        self.assertIn('Bahasa Indonesia',pp.script_prompt('Test','',15))

    def test_silent_mode_creates_silence_without_tts_or_music(self):
        plan=vd.normalize_scene_plan({'speech':speech.build(mode='none')},'Test','Tidak dibacakan.',2)
        with tempfile.TemporaryDirectory() as temp,patch.object(vd,'resolve_python',side_effect=AssertionError('No TTS')),patch.object(vd,'_write_procedural_audio',side_effect=AssertionError('No music')):
            audio=vd._build_audio(Path(temp),plan)
            with wave.open(str(audio)) as wav:
                self.assertEqual(wav.getnframes()/wav.getframerate(),2)
                self.assertFalse(any(wav.readframes(wav.getnframes())))

    def test_voice_only_alignment_uses_selected_voice_and_never_generates_bed(self):
        if not shutil.which('ffmpeg'):self.skipTest('FFmpeg unavailable')
        original_run=vd.subprocess.run
        for language in ('id','en'):
            plan=vd.normalize_scene_plan({'speech':speech.build(language),'scenes':[{'start':0,'end':3,'narration':'Narasi yang disetujui.','soundCue':'soft chime'}]},'Test','',3)
            with tempfile.TemporaryDirectory() as temp,patch.object(vd,'_write_procedural_audio',side_effect=AssertionError('Music forbidden')):
                def run(command,*args,**kwargs):
                    if len(command)>1 and str(command[1]).endswith('speech_worker.py'):
                        lines=json.loads(Path(command[2]).read_text());self.assertEqual(lines[0]['voice'],speech.VOICES[language])
                        out=Path(command[3]);out.mkdir()
                        with wave.open(str(out/'scene-1.wav'),'wb') as wav:
                            wav.setparams((1,2,24000,0,'NONE','not compressed'))
                            wav.writeframes(b''.join(int(math.sin(i*2*math.pi*220/24000)*6000).to_bytes(2,'little',signed=True) for i in range(24000)))
                        return None
                    return original_run(command,*args,**kwargs)
                with patch.object(vd.subprocess,'run',side_effect=run):audio=vd._build_audio(Path(temp),plan)
                self.assertFalse((Path(temp)/'music-foley.wav').exists())
                self.assertTrue((Path(temp)/'sound-effects.wav').is_file())
                with wave.open(str(audio)) as wav:self.assertAlmostEqual(wav.getnframes()/wav.getframerate(),3,places=2)

    def test_worker_rejects_path_ids_before_network_or_file_creation(self):
        import speech_worker
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'lines.json';out=root/'output'
            source.write_text(json.dumps([{'id':'../escape','text':'Halo','voice':'id-ID-ArdiNeural','rate':'+0%'}]))
            with patch('sys.argv',['speech_worker.py',str(source),str(out)]),patch.object(speech_worker.asyncio,'run') as network:
                with self.assertRaises(ValueError):speech_worker.main()
                network.assert_not_called()
            self.assertFalse(out.exists())
