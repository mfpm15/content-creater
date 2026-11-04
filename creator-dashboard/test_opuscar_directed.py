import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import opuscar_scene_spec as spec
import opuscar_quality_gate as gate
import video_drafter as vd


ROOT=Path(__file__).parent


def fixture():
    raw=json.loads((ROOT/'fixtures'/'opuscar-mechanical-audit.json').read_text(encoding='utf-8'))
    return vd.normalize_scene_plan(raw,raw['topic'],'',raw['duration'])


class DirectedSceneTests(unittest.TestCase):
    def test_audit_nineteen_shots_are_distinct_and_have_action_beats(self):
        report=spec.audit(fixture())
        self.assertEqual(report['issues'],[])
        self.assertEqual(report['directedScenes'],19)
        self.assertGreaterEqual(report['actionDiversity'],.7)
        self.assertGreaterEqual(len(report['cameraGrammars']),4)
        for shot in report['specs']:
            self.assertEqual(set(shot['beats']),{'anticipation','action','followThrough'})
        self.assertEqual(report['specs'][17]['object'],'seal') # mastery is not mast

    def test_same_family_different_subject_produces_different_structure_and_action(self):
        plan=fixture();lock=plan['scenes'][6];capsule=plan['scenes'][5]
        self.assertEqual(lock['visualFamily'],capsule['visualFamily'])
        self.assertNotEqual(spec.interpret(lock)['structureSignature'],spec.interpret(capsule)['structureSignature'])
        self.assertNotEqual(spec.interpret(lock)['motionSignature'],spec.interpret(capsule)['motionSignature'])
        self.assertIn('data-action="shear"',vd._visual_markup(lock,0))
        self.assertIn('data-action="travel"',vd._visual_markup(capsule,0))

    def test_layering_continuity_and_deterministic_document(self):
        plan=fixture();document=vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'])
        self.assertEqual(document,vd.generate_composition(copy.deepcopy(plan),vd.ASPECT_RATIOS['9:16']))
        for layer in ('scene-background','scene-midground','scene-foreground'):
            self.assertEqual(document.count(f'class="{layer}"'),19)
        self.assertEqual(document.count('data-continuity="steel-link"'),17)
        self.assertEqual(document.count('data-continuity="defense-wedge"'),2)
        for token in ('class="process-node','class="constellation-viz','class="compare-side','scene-orbit','scanner-line'):
            self.assertNotIn(token,document)

    def test_unrecognized_action_blocks_review_instead_of_silently_claiming_support(self):
        plan=fixture();plan['scenes'][0]['action']='dances a waltz'
        self.assertTrue(spec.audit(plan)['issues'])
        plan['scenes'][0]['action']='opens'
        self.assertIn('Unsupported object/action',spec.audit(plan)['issues'][0]['reason'])

    def test_no_invented_counts_and_explicit_controls_take_precedence(self):
        shot=fixture()['scenes'][12]
        self.assertEqual(spec.interpret(shot)['count'],7)
        shot.update(subject='balance scale',directionSubject='balance scale',renderControls={
            'camera':'locked','strength':.2,'lighting':'soft','transition':'cut'})
        interpreted=spec.interpret(shot)
        self.assertEqual(interpreted['count'],2)
        self.assertEqual(interpreted['camera'],'locked')
        self.assertEqual(interpreted['transition'],'cut')
        self.assertEqual(interpreted['strength'],.2)

    def test_directorial_subject_survives_roundtrip_and_injection_is_not_executable(self):
        plan=fixture();shot=plan['scenes'][0]
        text='Steel chain link '+('</script><script>alert(1)</script>'*4)
        shot.update(subject=text,directionSubject=text,action='pulls taut')
        normalized=vd.normalize_scene_plan(plan,plan['topic'],'',95)
        self.assertEqual(normalized['scenes'][0]['directionSubject'],text)
        self.assertEqual(normalized,vd.normalize_scene_plan(normalized,plan['topic'],'',95))
        self.assertNotIn('<script>alert(1)</script>',vd.generate_composition(normalized,vd.ASPECT_RATIOS['9:16']))
        normalized['scenes'][0]['continuityToken']='"><script>'
        with self.assertRaises(ValueError):spec.interpret(normalized['scenes'][0])

    def test_even_nonmechanical_opuscar_plans_require_visual_review(self):
        plan=vd.normalize_scene_plan({'scenes':[{'narration':'Alam','visual':'Hutan'}]},'Alam','',5)
        self.assertTrue(gate.required(plan))
        self.assertEqual(spec.audit(plan)['directedScenes'],0)

    def test_unknown_family_cannot_escape_timeline_javascript(self):
        plan=vd.normalize_scene_plan({'scenes':[{'narration':'Test','onScreenText':'Test',
            'visualFamily':"');alert(42);//"}]},'Test','',5)
        document=vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'])
        self.assertNotIn("alert(42)",document)

    def test_unknown_process_is_editorial_not_three_fake_steps(self):
        scene={'type':'process','visualFamily':'process','visual':'An unknown abstraction','narration':'Text',
               'onScreenText':'Unknown'}
        self.assertIn('data-interpretation="unsupported"',vd._visual_markup(scene,0))
        self.assertNotIn('process-node',vd._visual_markup(scene,0))

    def test_repeated_drawing_structure_is_rejected(self):
        plan=fixture();plan['scenes'][0:3]=[copy.deepcopy(plan['scenes'][0]) for _ in range(3)]
        self.assertTrue(any('consecutive' in row['reason'] for row in spec.audit(plan)['issues']))


class VisualApprovalTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PIL'),'Optional Pillow runtime')
    def test_raster_tolerance_rejects_real_displacement_or_large_color_change(self):
        from PIL import Image
        first=Image.new('RGB',(100,100),'black');second=first.copy()
        second.putpixel((10,10),(2,2,2))
        self.assertTrue(gate.compare_pixels(first,second)['withinTolerance'])
        second.putpixel((10,10),(3,3,3))
        self.assertFalse(gate.compare_pixels(first,second)['withinTolerance'])
        first.putpixel((50,50),(255,255,255));second=Image.new('RGB',(100,100),'black');second.putpixel((51,50),(255,255,255))
        self.assertFalse(gate.compare_pixels(first,second)['withinTolerance'])

    def test_missing_stale_failed_review_cannot_be_approved(self):
        document='trusted composition'
        for review in (None,{'status':'sampled','digest':'old','issues':[]},
                       {'status':'unmeasured','digest':gate.digest(document)},
                       {'status':'sampled','digest':gate.digest(document),'issues':[{'reason':'overflow'}]}):
            with self.subTest(review=review),self.assertRaises(ValueError):gate.verify(document,review)
        gate.verify(document,{'status':'sampled','digest':gate.digest(document),'issues':[]})

    def test_api_approval_and_worker_both_block_unreviewed_render(self):
        plan=fixture();job={'jobId':'abc','engine':'opuscar','scenePlan':plan,'aspect':'9:16',
                          'revision':2,'status':'awaiting_storyboard','model':'','topic':plan['topic'],'duration':95}
        with tempfile.TemporaryDirectory() as folder,patch.object(vd,'JOBS',{'abc':job}),patch.object(vd,'JOB_DIR',Path(folder)),patch.object(vd,'_build_audio') as audio,patch.object(vd.subprocess,'run') as render:
            with self.assertRaises(ValueError):vd.approve_job('abc','storyboard',2)
            vd._continue_job('abc','storyboard')
            self.assertEqual(vd.JOBS['abc']['status'],'failed')
            audio.assert_not_called();render.assert_not_called()

    def test_edits_invalidate_visual_digest_and_two_approvals(self):
        plan=fixture();job={'jobId':'abc','engine':'opuscar','scenePlan':plan,'aspect':'9:16',
            'revision':2,'status':'awaiting_storyboard','model':'','topic':plan['topic'],'duration':95,
            'visualReview':{'status':'sampled'},'visualFrames':['old'],'visualContactSheet':'old','approvals':{'scene_plan':2}}
        changed=copy.deepcopy(plan);changed['scenes'][0]['onScreenText']='Revised heading'
        with tempfile.TemporaryDirectory() as folder,patch.object(vd,'JOBS',{'abc':job}),patch.object(vd,'JOB_DIR',Path(folder)):
            result=vd.update_job_plan('abc',{'stage':'storyboard','revision':2,'scenePlan':changed})
            self.assertEqual(result['status'],'awaiting_scene_plan')
            self.assertEqual(result['approvals'],{})
            self.assertNotIn('visualReview',result)
            self.assertEqual(result['revision'],3)

    @unittest.skipUnless(os.getenv('GSAP_TEST_SCRIPT'),'Optional real SDK/browser review')
    def test_real_browser_gate_checks_all_nineteen_scenes_and_repeat_tolerance(self):
        plan=fixture()
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);(target/'index.html').write_text(vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16']),encoding='utf-8')
            report=gate.inspect(target,plan,vd.ASPECT_RATIOS['9:16'])
            self.assertEqual(report['status'],'sampled',report.get('issues'))
            self.assertEqual(report['observedFrames'],57)
            self.assertEqual(len(report['frames']),19)
            self.assertTrue((target/'contact-sheet.png').is_file())
            gate.verify((target/'index.html').read_text(encoding='utf-8'),report)


if __name__=='__main__':unittest.main()
