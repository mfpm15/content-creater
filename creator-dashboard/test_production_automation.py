import copy
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import article_tools
import evidence
import remotion_adapter
import video_bundle
import video_delivery
import video_drafter as vd


def example():
    return vd.normalize_scene_plan({'audioMode':'music','scenes':[
        {'start':0,'end':1,'narration':'Sebuah proses dimulai.','onScreenText':'MULAI','visualFamily':'process'},
        {'start':1,'end':2,'narration':'Hasilnya 25 persen.','onScreenText':'HASIL 25%','visualFamily':'data'}]},'Studio test','',2)


class ProductionAutomationTests(unittest.TestCase):
    def test_manifest_preserves_complete_text_frames_and_brand(self):
        plan=example();plan['brand']={'name':'Studio','font':'Georgia','wordmark':'Brand','accent':'#112233'}
        props,report=remotion_adapter.manifest(plan,{'width':320,'height':568})
        self.assertEqual(props['totalFrames'],60)
        self.assertEqual([(s['startFrame'],s['endFrame']) for s in props['shots']],[(0,30),(30,60)])
        self.assertEqual(' '.join(c['text'] for c in props['captions']),' '.join(s['narration'] for s in plan['scenes']))
        self.assertEqual(props['brand']['font'],'Georgia')
        self.assertIn('25%',props['shots'][1]['subject'])
        self.assertTrue(all(row['method'].startswith('estimated') for row in report['caption_timing']))
        self.assertEqual(vd.audio_manifest(plan)['voice'],[])

    def test_gap_too_short_and_nonfinite_controls_are_rejected(self):
        for mutate in (lambda p:p['scenes'][1].update(start=1.1),lambda p:p['scenes'][1].update(end=1),
                       lambda p:p['scenes'][0].update(renderControls={'strength':math.inf})):
            plan=example();mutate(plan)
            with self.assertRaises(ValueError):remotion_adapter.manifest(plan,{'width':320,'height':568})

    def test_metric_labels_preserve_signs_and_do_not_duplicate_headline_and_narration(self):
        plan=example()
        props,_=remotion_adapter.manifest(plan,{'width':320,'height':568})
        self.assertEqual(props['shots'][1]['subject'],'25%')
        plan['scenes'][1]['onScreenText']='Profit -3,5%'
        props,_=remotion_adapter.manifest(plan,{'width':320,'height':568})
        self.assertEqual(props['shots'][1]['subject'],'-3,5%')
        plan['scenes'][1].update(onScreenText='Rp2.000',narration='Nilai Rp2.000')
        props,_=remotion_adapter.manifest(plan,{'width':320,'height':568})
        self.assertEqual(props['shots'][1]['subject'],'')

    def test_explicit_cues_keep_timestamp_provenance(self):
        plan=example();scene=plan['scenes'][0]
        scene['wordCues']=[{'word':word,'start':i*.25,'end':i*.25+.2} for i,word in enumerate(scene['narration'].split())]
        props,report=remotion_adapter.manifest(plan,{'width':320,'height':568})
        self.assertEqual(props['captions'][0]['endFrame'],21)
        self.assertTrue(report['caption_timing'][0]['method'].startswith('supplied'))

    def test_delivery_uses_shared_specs_without_claiming_official_limits(self):
        reports=video_delivery.evaluate({'width':1080,'height':1920,'avg_frame_rate':'30/1'},60,
                                       {'status':'measured','integrated_lufs':-14,'true_peak_dbfs':-1.5})
        self.assertTrue(all(row['status']=='passed_working_profile' for row in reports.values()))
        self.assertTrue(all(row['spec_verified_official'] is False for row in reports.values()))
        low=video_delivery.evaluate({'width':320,'height':568,'avg_frame_rate':'0/0'},120,{'status':'unmeasured'})
        self.assertEqual(low['reels']['status'],'needs_attention')

    def test_editorial_plan_prioritizes_sources_without_changing_or_auto_verifying(self):
        article={'lang':'Indonesia','blocks':[{'type':'h2','text':'Bagian pertama'},
            {'type':'p','text':'Di era digital ini, hasilnya 25% [9].'},
            {'type':'h2','text':'Bagian kedua'},{'type':'p','text':'Simpan dokumen dengan rapi.'}]}
        original=copy.deepcopy(article)
        report=article_tools.improvement_plan(article,evidence.audit(article))
        self.assertTrue(report['requires_approval'])
        self.assertEqual(report['sections'][0]['section'],0)
        self.assertTrue(report['sections'][0]['can_propose_language'])
        self.assertEqual(report['sections'][0]['source_checks'],1)
        self.assertEqual(article,original)

    def test_aspect_variant_preserves_remotion_audio_and_review(self):
        plan=example()
        with tempfile.TemporaryDirectory() as folder,patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',Path(folder)),patch.object(vd,'get_video',return_value={'engine':'remotion','scenePlan':plan}):
            job=vd.create_aspect_jobs('source',['1:1'])[0]
            self.assertEqual(job['audioMode'],'music')
            self.assertEqual(job['approvals'],{})
            saved=vd.update_job_plan(job['jobId'],{'stage':'scene_plan','revision':0,'scenePlan':plan})
            self.assertEqual(saved['status'],'awaiting_scene_plan')

    def test_real_remotion_pipeline_two_approvals_audio_review_and_bundle(self):
        if remotion_adapter.runtime_issues():self.skipTest('Optional Remotion runtime unavailable')
        with tempfile.TemporaryDirectory(prefix='studio path ') as folder:
            root=Path(folder)
            with patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',root/'jobs'),patch.object(vd,'VIDEOS_DIR',root/'videos'),patch.dict(vd.ASPECT_RATIOS,{'9:16':{'id':'9:16','width':320,'height':568,'label':'Test'}}),patch.object(vd,'_call_9router',side_effect=AssertionError('Offline only')),patch.object(vd,'_research_web',side_effect=AssertionError('Offline only')),patch.object(vd,'resolve_python',side_effect=AssertionError('Music must not invoke TTS')),patch.dict(os.environ,{'VIDEO_REVIEW_ALLOW_NO_SANDBOX':'1'}):
                with patch.object(vd.threading.Thread,'start'):
                    job=vd.start_job({'engine':'remotion','topic':'Studio acceptance','voiceMode':'music','researchMode':'provided',
                                     'script':'0-1 Narasi: Proses dimulai.\nTeks layar: MULAI\n\n1-2 Narasi: Hasilnya 25 persen.\nTeks layar: HASIL 25%'})
                key=job['jobId'];vd._run_job(key)
                job=vd.job_status(key);self.assertEqual(job['status'],'awaiting_scene_plan',job.get('error'))
                self.assertEqual(job['scenePlan']['audioMode'],'music')
                for stage in ('scene_plan','storyboard'):
                    with patch.object(vd.threading.Thread,'start'):vd.approve_job(key,stage,job['revision'])
                    vd._continue_job(key,stage);job=vd.job_status(key)
                self.assertEqual(job['status'],'succeeded',job.get('error'))
                target=vd.VIDEOS_DIR/job['video']['slug']
                review=json.loads((target/'review.json').read_text())
                self.assertEqual(review['audio']['status'],'measured')
                self.assertLessEqual(abs(review['audio']['integrated_lufs']+14),2)
                self.assertLessEqual(review['audio']['true_peak_dbfs'],-.5)
                self.assertEqual(review['video_format']['codec_name'],'h264')
                self.assertEqual(review['video_format']['pix_fmt'],'yuv420p')
                self.assertEqual(review['video_format']['color_space'],'bt709')
                self.assertEqual(json.loads((target/'audio-mastering.json').read_text())['method'],'two_pass_loudnorm')
                self.assertEqual(len(review['remotion']['frames']),2)
                self.assertGreater(review['remotion']['layout']['observed_frames'],0)
                self.assertEqual(review['remotion']['layout']['issues'],[])
                with video_bundle.build(target) as archive:self.assertGreater(archive.stat().st_size,10000)


if __name__=='__main__':unittest.main()
