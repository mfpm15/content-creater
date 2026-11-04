import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import opuscar_scene_spec as mechanical
import renderer_contract as contract
import video_drafter as vd


class RendererContractTests(unittest.TestCase):
    def plan(self,**scene):
        return vd.normalize_scene_plan({'scenes':[{'start':0,'end':5,'narration':'Pertahankan narasi asli.',**scene}]},'Test','',5)

    def test_every_advertised_mechanical_action_is_interpreted(self):
        for obj,actions in mechanical.COMPATIBLE.items():
            for action in actions:
                with self.subTest(object=obj,action=action):
                    p=self.plan(subject=contract.SUBJECTS[obj],action=action)
                    self.assertFalse(mechanical.interpret(p['scenes'][0])['issues'])
                    for engine in ('opuscar','threejs'):self.assertFalse(contract.inspect(p,engine)['errors'])
        self.assertEqual(mechanical.interpret(self.plan(subject='modules',action='expand')['scenes'][0])['action'],'expand')

    def test_opuscar_diagnostics_match_actual_markup_fallbacks(self):
        for kind in ('story','data','call-to-action'):
            for family in (*sorted(contract.FAMILIES),'data','process','comparison','constellation','unknown'):
                with self.subTest(kind=kind,family=family):
                    p=self.plan(type=kind,visualFamily=family)
                    actual='data-interpretation="unsupported"' in vd._visual_markup(p['scenes'][0],0)
                    self.assertEqual(bool(contract.inspect(p,'opuscar')['errors']),actual)

    def test_editorial_fallback_is_reported_and_intentional_text_is_supported(self):
        p=self.plan(subject='butterfly',visualFamily='nature')
        self.assertEqual(contract.inspect(p,'threejs')['warnings'][0]['code'],'editorial_fallback')
        p['scenes'][0]['visualFamily']='kinetic-type'
        self.assertEqual(contract.inspect(p,'threejs')['status'],'supported')

    def test_diagram_labels_and_continuous_concepts_are_checked(self):
        p=self.plan(visualFamily='process')
        for engine in ('remotion','lottie'):
            self.assertEqual(contract.inspect(p,engine)['warnings'][0]['code'],'missing_diagram_labels')
        p['scenes'][0]['diagram']={'kind':'process','labels':['Input','Hasil']}
        self.assertEqual(contract.inspect(p,'remotion')['status'],'supported')
        self.assertTrue(contract.inspect(p,'continuous')['errors'])
        p['motionDesign']={'concept':'trace'}
        self.assertEqual(contract.inspect(p,'continuous')['status'],'supported')

    def test_invalid_native_action_blocks_approval_and_worker_before_audio(self):
        p=self.plan(subject='prism',action='block')
        key='a'*32;job={'jobId':key,'pipelineVersion':2,'scenePlan':p,'engine':'threejs','aspect':'9:16',
            'topic':'Test','duration':5,'revision':0,'status':'awaiting_scene_plan','approvals':{}}
        with tempfile.TemporaryDirectory() as folder,patch.object(vd,'JOBS',{key:job}),patch.object(vd,'JOB_DIR',Path(folder)):
            with self.assertRaisesRegex(ValueError,'belum dapat dirender'):vd.approve_job(key,'scene_plan',0)
            with patch.object(vd,'_build_audio') as audio,patch.object(vd.subprocess,'run') as render:
                vd._continue_job(key,'storyboard')
            audio.assert_not_called();render.assert_not_called()
            vd.JOBS[key]['status']='awaiting_scene_plan'
            fixed=copy.deepcopy(p);fixed['scenes'][0]['action']='refract'
            updated=vd.update_job_plan(key,{'stage':'scene_plan','revision':0,'scenePlan':fixed})
            self.assertEqual(updated['rendererReview']['status'],'supported')
            with patch.object(vd.threading.Thread,'start'):vd.approve_job(key,'scene_plan',updated['revision'])

    def test_planner_receives_renderer_specific_capabilities(self):
        for engine in vd.ENGINES:
            text=contract.planner_instruction(engine)
            self.assertIn('KONTRAK ENGINE: '+engine,text)
        self.assertIn('lock pins',contract.planner_instruction('threejs'))
        self.assertIn('diagram',contract.planner_instruction('remotion'))
        self.assertIn('trace/focus/assemble',contract.planner_instruction('continuous'))


    def test_data_without_literal_numbers_is_flagged_without_inventing_values(self):
        p=self.plan(visualFamily='data',onScreenText='Ringkasan')
        for engine in ('opuscar','remotion'):
            self.assertEqual(contract.inspect(p,engine)['warnings'][0]['code'],'missing_literal_metric')
        p['scenes'][0]['onScreenText']='Perubahan -3,5%'
        self.assertEqual(contract.literal_numbers(p['scenes'][0]),['-3,5%'])
        self.assertFalse(contract.inspect(p,'opuscar')['warnings'])
