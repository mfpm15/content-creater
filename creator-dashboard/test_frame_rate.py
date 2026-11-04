import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import video_review

import frame_rate
import continuous_motion as motion
import lottie_adapter
import remotion_adapter
import video_drafter as vd


def plan(fps):
    return vd.normalize_scene_plan({'fps':fps,'motionDesign':{'concept':'trace','voiceMode':'music'},
        'scenes':[{'start':0,'end':1,'narration':'Awali dari ide.','onScreenText':'Ide'},
                  {'start':1,'end':2,'narration':'Bangun sebuah cerita.','onScreenText':'Cerita'}]},'Frame test','',2)


class FrameRateTests(unittest.TestCase):
    def test_invalid_rates_fail_and_legacy_plan_retains_30(self):
        self.assertEqual(frame_rate.get({}),30)
        for value in (True,30.0,'60',None,0,59,120):
            with self.subTest(value=value),self.assertRaises(ValueError):plan(value)

    def test_new_job_defaults_to_60_and_aspect_variant_preserves_rate(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',Path(folder)),patch.object(vd.threading.Thread,'start'):
            for engine in vd.ENGINES:
                key=vd.start_job({'topic':'Local','script':'0-2 Narasi: Sebuah ide.','engine':engine,'researchMode':'provided','motionConcept':'trace'})['jobId']
                vd._run_job(key);job=vd.job_status(key)
                self.assertEqual(job['status'],'awaiting_scene_plan',job.get('error'))
                self.assertEqual(job['fps'],60);self.assertEqual(job['scenePlan']['fps'],60)
                if engine=='continuous':self.assertEqual(job['motionDesign']['fps'],60)
            with patch.object(vd,'get_video',return_value={'engine':'lottie','scenePlan':job['scenePlan']}):
                variant=vd.create_aspect_jobs('test',['1:1'])[0]
                self.assertEqual(variant['scenePlan']['fps'],60);self.assertEqual(variant['fps'],60)

    def test_adapters_preserve_seconds_and_emit_selected_rate(self):
        for fps in (30,60):
            p=plan(fps);props,_=remotion_adapter.manifest(p,{'width':320,'height':568})
            self.assertEqual(props['fps'],fps);self.assertEqual(props['totalFrames'],2*fps)
            self.assertEqual(props['shots'][1]['startFrame'],fps)
            self.assertEqual(props['captions'][-1]['endFrame'],2*fps)
            anim=lottie_adapter.build(p,{'width':320,'height':568})
            self.assertEqual(anim['fr'],fps);self.assertEqual(anim['op']/anim['fr'],2)
            self.assertEqual(p['motionDesign']['fps'],fps)
            for engine in ('opuscar','threejs'):
                self.assertIn(f'data-fps="{fps}"',vd.generate_composition(p,{'width':320,'height':568},engine=engine))
        a=lottie_adapter.build(plan(30),{'width':320,'height':568})
        b=lottie_adapter.build(plan(60),{'width':320,'height':568})
        for left,right in zip(a['layers'],b['layers']):
            self.assertEqual(left['ip']/30,right['ip']/60)
            for prop in ('o','s'):
                if not left['ks'][prop]['a']:
                    self.assertEqual(left['ks'][prop],right['ks'][prop]);continue
                for x,y in zip(left['ks'][prop]['k'],right['ks'][prop]['k']):
                    self.assertEqual(x['t']/30,y['t']/60)

    def test_60fps_cache_matches_uncached_encoded_frames(self):
        if motion.runtime_issues():self.skipTest('Browser/FFmpeg unavailable')
        p=plan(60);aspect={'width':160,'height':288}
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'VIDEO_REVIEW_ALLOW_NO_SANDBOX':'1'}):
            paths=[]
            for reuse in (True,False):
                target=Path(folder)/str(reuse);target.mkdir();(target/'index.html').write_text(motion.composition(p,aspect))
                path,report=motion.render(target,p,aspect,reuse_static_frames=reuse)
                self.assertEqual(report['fps'],60);self.assertEqual(report['frames'],120)
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams'][0]
                self.assertEqual(probe['avg_frame_rate'],'60/1')
                output=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','framemd5','-'])
                paths.append([row for row in output.splitlines() if not row.startswith(b'#')])
            self.assertEqual(len(paths[0]),120);self.assertEqual(*paths)


    def test_review_flags_output_that_does_not_match_approved_fps(self):
        data={'format':{'duration':'2'},'streams':[
            {'codec_type':'video','width':320,'height':568,'avg_frame_rate':'30/1'},
            {'codec_type':'audio'}]}
        with tempfile.TemporaryDirectory() as folder,patch.object(video_review.shutil,'which',return_value='/test/ffprobe'),patch.object(video_review,'_audio',return_value={'status':'measured','integrated_lufs':-14,'true_peak_dbfs':-1}):
            for fps in (30,60):
                with patch.object(video_review.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(data).encode())):
                    report=video_review.review(Path(folder)/'video.mp4',2,plan(fps))
                self.assertEqual(report['frame_rate']['status'],'matched' if fps==30 else 'mismatch')
                self.assertEqual('Frame rate differs from approved plan' in report['issues'],fps==60)
