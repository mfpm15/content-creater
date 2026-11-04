import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import video_drafter as vd
import video_preproduction as pp


class PreproductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        for name,value in [('JOBS',{}),('JOB_DIR',Path(self.temp.name)/'jobs'),('VIDEOS_DIR',Path(self.temp.name)/'videos')]:
            mock=patch.object(vd,name,value);mock.start();self.addCleanup(mock.stop)
        mock=patch.object(vd.threading.Thread,'start');mock.start();self.addCleanup(mock.stop)

    def start(self,**payload):
        return vd.start_job({'topic':'Rantai','engine':'lottie','duration':15,**payload})['jobId']

    def test_title_first_generates_narration_then_binds_scene_planner(self):
        key=self.start()
        responses=[{'narration':'Nilai -3,5%. Jangan hapus data.'},{'scenes':[
            {'start':0,'end':7,'narration':'Nilai -3,5%.','onScreenText':'-3,5%'},
            {'start':7,'end':15,'narration':'Jangan hapus data.','onScreenText':'Pertahankan data'}]}]
        with patch.object(vd,'_call_9router',side_effect=[json.dumps(r) for r in responses]) as model:
            vd._run_job(key)
        job=vd.job_status(key);self.assertEqual(job['status'],'awaiting_scene_plan',job.get('error'))
        self.assertEqual(model.call_count,2)
        self.assertIn('TAHAP 1',model.call_args_list[0].args[0])
        self.assertIn('Nilai -3,5%. Jangan hapus data.',model.call_args_list[1].args[0])
        pp.verify_narration(job['narrationDraft'],job['scenePlan'])

    def test_scene_planner_cannot_drop_negations_numbers_or_sentences(self):
        for changed in ('Nilai 3,5%. Jangan hapus data.','Nilai -3,5%. Hapus data.','Nilai -3,5%.'):
            key=self.start()
            with patch.object(vd,'_call_9router',side_effect=[json.dumps({'narration':'Nilai -3,5%. Jangan hapus data.'}),
                json.dumps({'scenes':[{'start':0,'end':15,'narration':changed}]})]):vd._run_job(key)
            job=vd.job_status(key);self.assertEqual(job['status'],'failed')
            self.assertIn('narasi',job['error'])
            self.assertEqual(job['narrationDraft']['text'],'Nilai -3,5%. Jangan hapus data.')

    def test_long_user_script_never_loses_tail_and_never_calls_provider(self):
        script=' '.join(f'Butir {i} tidak boleh hilang.' for i in range(1,31))
        key=self.start(script=script,researchMode='provided')
        with patch.object(vd,'_call_9router',side_effect=AssertionError('Offline script')):vd._run_job(key)
        job=vd.job_status(key);self.assertEqual(job['status'],'awaiting_scene_plan',job.get('error'))
        self.assertEqual(len(job['scenePlan']['scenes']),12)
        self.assertEqual(pp.canonical(script),pp.canonical(' '.join(s['narration'] for s in job['scenePlan']['scenes'])))

    def test_failed_breakdown_reuses_saved_narration_on_resume(self):
        key=self.start()
        with patch.object(vd,'_call_9router',side_effect=[json.dumps({'narration':'Narasi yang disimpan.'}),RuntimeError('Model unavailable')]):vd._run_job(key)
        vd.resume_job(key,0)
        with patch.object(vd,'_call_9router',return_value=json.dumps({'scenes':[{'start':0,'end':15,'narration':'Narasi yang disimpan.'}]})) as model:vd._run_job(key)
        self.assertEqual(model.call_count,1);self.assertEqual(vd.job_status(key)['status'],'awaiting_scene_plan')

    def test_prompt_packet_is_reviewed_and_invalidated_by_edit(self):
        key=self.start(script='Rantai bergerak.',researchMode='provided')
        vd._run_job(key);vd._continue_job(key,'scene_plan');job=vd.job_status(key)
        self.assertEqual(job['status'],'awaiting_storyboard')
        pp.verify_packet(job['productionPacket'],job['scenePlan'],'lottie','9:16')
        self.assertIn('productionPrompt',job['storyboard'][0])
        raw=copy.deepcopy(job['scenePlan']);raw['scenes'][0]['narration']='Narasi yang direvisi.'
        result=vd.update_job_plan(key,{'stage':'storyboard','revision':0,'scenePlan':raw})
        self.assertNotIn('productionPacket',result)
        self.assertEqual(result['narrationDraft']['text'],'Narasi yang direvisi.')
        self.assertEqual(result['status'],'awaiting_scene_plan')

    def test_api_and_worker_reject_missing_or_stale_prompts_before_audio(self):
        key=self.start(script='Rantai bergerak.',researchMode='provided')
        vd._run_job(key);vd._continue_job(key,'scene_plan');job=vd.job_status(key)
        for packet in (None,{**job['productionPacket'],'fps':30}):
            vd.JOBS[key].update(status='awaiting_storyboard',productionPacket=packet)
            with self.assertRaises(ValueError):vd.approve_job(key,'storyboard',0)
            with patch.object(vd,'_build_audio') as audio,patch.object(vd.subprocess,'run') as renderer:
                vd._continue_job(key,'storyboard')
            audio.assert_not_called();renderer.assert_not_called()

    def test_packet_artifacts_export_for_local_pipeline(self):
        key=self.start(script='Sebuah narasi.',researchMode='provided')
        vd._run_job(key);vd._continue_job(key,'scene_plan');vd._continue_job(key,'storyboard')
        job=vd.job_status(key);self.assertEqual(job['status'],'succeeded',job.get('error'))
        root=vd.VIDEOS_DIR/job['video']['slug']
        self.assertTrue((root/'narration.json').is_file());self.assertTrue((root/'production-prompts.json').is_file())
        from video_bundle import build
        import zipfile
        with build(root) as path,zipfile.ZipFile(path) as bundle:
            self.assertIn('narration.json',bundle.namelist());self.assertIn('production-prompts.json',bundle.namelist())


    def test_creative_brief_is_not_spoken_and_timings_cannot_drift(self):
        key=self.start(script='Narasi asli.',creativeBrief='Audiens pemula; warna hangat.',researchMode='provided')
        vd._run_job(key);job=vd.job_status(key)
        self.assertEqual(job['narrationDraft']['text'],'Narasi asli.')
        self.assertEqual(job['scenePlan']['creativeBrief'],'Audiens pemula; warna hangat.')
        for scene in ({'start':1,'end':15,'narration':'Narasi asli.'},{'start':0,'end':16,'narration':'Narasi asli.'}):
            plan=vd.normalize_scene_plan({'scenes':[scene]},'Test','',15)
            with self.assertRaises(ValueError):pp.verify_timing(plan,15)

    def test_packet_is_deterministic_and_bound_to_every_engine_and_aspect(self):
        plan=vd.normalize_scene_plan({'scenes':[{'start':0,'end':15,'narration':'Rantai bergerak.','subject':'chain link','action':'tension'}]},'Rantai','',15)
        original=copy.deepcopy(plan)
        for engine in vd.ENGINES:
            packet=pp.compile_packet(plan,engine,'9:16')
            pp.verify_packet(packet,plan,engine,'9:16')
            self.assertEqual(packet,pp.compile_packet(plan,engine,'9:16'))
            with self.assertRaises(ValueError):pp.verify_packet(packet,plan,engine,'16:9')
        self.assertEqual(plan,original)
