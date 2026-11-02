import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import continuous_motion as motion
import video_bundle
import video_drafter as vd


def example():
    return vd.normalize_scene_plan({'creativeDirection':{'logline':'Satu proses berlanjut.'},
        'motionDesign':{'concept':'trace','voiceMode':'music'},
        'scenes':[{'start':0,'end':1,'narration':'Mulai.','onScreenText':'Ide','visual':'Penanda membuka jalur.','soundCue':'click'},
                  {'start':1,'end':2,'narration':'Hubungkan.','onScreenText':'Hasil','visual':'Jalur berlanjut.','soundCue':'chime'}]},'Test','',2)


class ContinuousMotionTests(unittest.TestCase):
    def setUp(self):
        self.workspace=tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root=Path(self.workspace.name)
        for item in [patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',self.root/'jobs'),patch.object(vd,'VIDEOS_DIR',self.root/'videos')]:
            item.start();self.addCleanup(item.stop)

    def test_three_concepts_require_explicit_valid_selection(self):
        plan=example()
        self.assertEqual(len({row['id'] for row in motion.CONCEPTS}),3)
        for concept in motion.CONCEPTS:
            cfg=motion.design({'concept':concept['id']},plan['scenes'],2)
            self.assertEqual(cfg['quality'],'draft')
        for raw in [{},{'concept':'<script>'},{'concept':'trace','restFraction':True},
                    {'concept':'trace','restFraction':float('nan')},{'concept':'trace','voiceMode':'upload'}]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):motion.design(raw,plan['scenes'],2)

    def test_gaps_and_incomplete_duration_are_rejected_without_retiming(self):
        plan=example();scenes=copy.deepcopy(plan['scenes'])
        scenes[1]['start']=1.1
        with self.assertRaises(ValueError):motion.design(plan['motionDesign'],scenes,2)
        self.assertEqual(scenes[1]['start'],1.1)
        with self.assertRaises(ValueError):motion.design(plan['motionDesign'],plan['scenes'],3)
        with self.assertRaisesRegex(ValueError,'12 beat'):
            motion.design({'concept':'assemble'},[{'start':i,'end':i+1} for i in range(13)],13)

    def test_beat_sheet_has_holds_and_exact_authored_boundaries(self):
        plan=example();sheet=motion.beat_sheet(plan)
        self.assertEqual(sheet['transitions'][0]['at'],1)
        self.assertEqual(len(sheet['beats']),2)
        self.assertTrue(all(beat['holdEnd']>beat['holdStart'] for beat in sheet['beats']))
        self.assertTrue(sheet['advisories'])
        self.assertEqual(plan['motionBeatSheet'],sheet)

    def test_safe_serialization_and_no_external_assets(self):
        plan=example();plan['scenes'][0]['narration']='</script><img src=x onerror=alert(1)>'
        plan['brand']={'name':'Kit','wordmark':'<img src=x>','accent':'#123456'}
        html=motion.composition(plan,{'width':320,'height':568})
        self.assertNotIn('</script><img',html)
        self.assertNotIn('<img src=x>',html)
        self.assertNotIn('<script src=',html)
        self.assertIn("connect-src 'none'",html)
        self.assertNotIn('Math.random(',html)
        self.assertNotIn('setInterval(',html)
        data=html.split('<script id="motion-data" type="application/json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(data)['scenes'][0]['narration'],plan['scenes'][0]['narration'])

    def test_edit_preserves_creative_direction_and_invalidates_changed_storyboard(self):
        plan=example();key='a'*32
        vd.JOBS[key]={'jobId':key,'engine':'continuous','duration':2,'topic':'Test','status':'awaiting_storyboard',
                      'scenePlan':plan,'revision':2,'approvals':{'scene_plan':2}}
        raw=copy.deepcopy(plan)
        unchanged=vd.update_job_plan(key,{'stage':'storyboard','revision':2,'scenePlan':raw})
        self.assertEqual(unchanged['status'],'awaiting_storyboard')
        self.assertEqual(unchanged['scenePlan']['creativeDirection'],plan['creativeDirection'])
        raw['scenes'][0]['visual']='Revisi yang diminta pengguna.'
        changed=vd.update_job_plan(key,{'stage':'storyboard','revision':2,'scenePlan':raw})
        self.assertEqual(changed['status'],'awaiting_scene_plan')
        self.assertEqual(changed['approvals'],{})
        with self.assertRaises(vd.RevisionConflict):vd.update_job_plan(key,{'stage':'scene_plan','revision':2,'scenePlan':raw})

    def test_music_manifest_does_not_claim_a_voice_track(self):
        manifest=vd.audio_manifest(example())
        self.assertEqual(manifest['voice'],[])
        self.assertEqual(manifest['voiceMode'],'music')
        self.assertFalse(manifest['music']['duckUnderVoice'])
        self.assertFalse(any(.05<t<.6 for t in manifest['music']['beat_markers']))

    def test_loopback_renderer_serves_one_file_and_requires_exact_host(self):
        source=self.root/'index.html';source.write_text('<h1>Composition</h1>')
        (self.root/'private.env').write_text('private fixture')
        with motion._serve(source) as uri:
            with urllib.request.urlopen(uri,timeout=5) as response:
                self.assertEqual(response.read(),b'<h1>Composition</h1>')
            base=uri.rsplit('/',1)[0]
            for url,headers in [(base+'/private.env',{}),(base+'/',{}),(uri,{'Host':'evil.example'})]:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=5)
                self.assertEqual(error.exception.code,404)

    def test_legacy_adapter_cannot_silently_disable_voice_with_motion_metadata(self):
        key='b'*32
        vd.JOBS[key]={'jobId':key,'engine':'opuscar','duration':2,'topic':'Test','status':'awaiting_scene_plan',
                      'scenePlan':example(),'revision':0,'approvals':{}}
        with self.assertRaisesRegex(ValueError,'hanya tersedia'):
            vd.update_job_plan(key,{'stage':'scene_plan','revision':0,'scenePlan':example()})

    def test_music_build_skips_tts_and_provider_environment(self):
        plan=example()
        with patch.object(vd,'resolve_python',return_value=Path('missing-python')),patch.object(vd,'_write_procedural_audio'),patch.object(vd.subprocess,'run') as run:
            vd._build_audio(self.root,plan)
            self.assertEqual(run.call_count,1)
            self.assertNotIn('tts_zh.py',' '.join(run.call_args.args[0]))

    def test_real_offline_mp4_two_approvals_and_production_bundle(self):
        missing=motion.runtime_issues()
        if missing:self.skipTest('Optional media runtime unavailable: '+', '.join(missing))
        aspect={'id':'9:16','width':160,'height':288,'label':'Small test'}
        with patch.dict(os.environ,{'VIDEO_REVIEW_ALLOW_NO_SANDBOX':'1'}),patch.dict(vd.ASPECT_RATIOS,{'9:16':aspect}),patch.object(vd,'_call_9router',side_effect=AssertionError('No LLM')),patch.object(vd,'_research_web',side_effect=AssertionError('No web')):
            with patch.object(vd.threading.Thread,'start'):
                result=vd.start_job({'topic':'Offline pipeline','engine':'continuous','motionConcept':'trace','voiceMode':'music',
                    'researchMode':'provided','script':'0-1 Narasi: Ide.\nTeks layar: Ide\nSFX: click\n\n1-2 Narasi: Hasil.\nTeks layar: Hasil\nSFX: chime'})
            key=result['jobId'];vd._run_job(key)
            job=vd.job_status(key);self.assertEqual(job['status'],'awaiting_scene_plan',job.get('error'))
            with patch.object(vd.threading.Thread,'start'):vd.approve_job(key,'scene_plan',job['revision'])
            vd._continue_job(key,'scene_plan')
            job=vd.job_status(key)
            with patch.object(vd.threading.Thread,'start'):vd.approve_job(key,'storyboard',job['revision'])
            vd._continue_job(key,'storyboard')
            job=vd.job_status(key);self.assertEqual(job['status'],'succeeded',job.get('error'))
            folder=vd.VIDEOS_DIR/job['video']['slug'];video=folder/'video.mp4'
            report=json.loads((folder/'review.json').read_text())
            self.assertTrue(report['motion_review']['deterministic_repeat'])
            self.assertEqual(report['motion_review']['rendered_pixel_motion']['status'],'measured')
            self.assertGreater(report['motion_review']['rendered_pixel_motion']['samples'],10)
            self.assertEqual(len(report['motion_review']['boundaries']),1)
            self.assertEqual(report['motion_review']['frames'],60)
            self.assertLess(report['motion_review']['captured_frames'],60)
            self.assertGreater(report['motion_review']['reused_static_frames'],0)
            self.assertEqual(report['motion_review']['boundaries'][0]['status'],'carried')
            with video.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
            self.assertEqual(report['artifact_sha256'],digest)
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))
            track=next(row for row in probe['streams'] if row['codec_type']=='video')
            self.assertEqual((track['width'],track['height'],track['r_frame_rate']),(160,288,'30/1'))
            self.assertTrue(any(row['codec_type']=='audio' for row in probe['streams']))
            reference=self.root/'uncached';reference.mkdir()
            (reference/'index.html').write_bytes((folder/'index.html').read_bytes())
            uncached,_=motion.render(reference,job['scenePlan'],aspect,reuse_static_frames=False)
            def decoded_hashes(path):
                output=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-an','-f','framemd5','-'])
                return [line for line in output.splitlines() if not line.startswith(b'#')]
            self.assertEqual(decoded_hashes(video),decoded_hashes(uncached))
            with video_bundle.build(folder) as archive:
                with zipfile.ZipFile(archive) as content:
                    self.assertIn('review.json',content.namelist())
                    self.assertEqual(json.loads(content.read('scene-plan.json'))['motionDesign']['concept'],'trace')
