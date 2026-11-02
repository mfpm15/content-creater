import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evidence
import scene_render
import video_drafter as vd


class StudioControlsTests(unittest.TestCase):
    def plan(self, controls=None):
        shot={'start':0,'end':5,'narration':'Satu bentuk berubah.','onScreenText':'Bentuk','visual':'Satu bentuk'}
        if controls is not None:shot['renderControls']=controls
        return vd.normalize_scene_plan({'scenes':[shot]},'Studio test','',5)

    def test_controls_roundtrip_and_legacy_remains_opt_in(self):
        legacy=self.plan()
        self.assertNotIn('renderControls',legacy['scenes'][0])
        plan=self.plan({'camera':'push-in','strength':.75,'lighting':'dramatic','transition':'slide'})
        self.assertEqual(plan,vd.normalize_scene_plan(plan,plan['topic'],'',5))
        for engine in ('opuscar','threejs'):
            document=vd.generate_composition(plan,{'width':320,'height':568},engine=engine)
            self.assertIn('attachAnimationClock(tl',document)
            self.assertNotEqual(document,vd.generate_composition(legacy,{'width':320,'height':568},engine=engine))
        two=vd.generate_composition(plan,{'width':320,'height':568})
        self.assertIn('contrast(1.35)',two)
        self.assertNotIn('yoyo:true, repeat:1',two)

    def test_untrusted_controls_cannot_become_javascript(self):
        for controls in (None,[],{'camera':'</script><script>alert(1)'},{'lighting':'url(https://bad.test)'},
                         {'strength':True},{'strength':math.nan},{'strength':math.inf},{'strength':-1},
                         {'strength':1.01},{'strength':'0.5'},{'customScript':'alert(1)'}, {'transition':{}}):
            with self.subTest(controls=controls),self.assertRaises(ValueError):scene_render.validate(controls)

    def test_unsupported_adapter_rejects_controls_before_saving(self):
        plan=self.plan()
        job={'jobId':'abc','topic':plan['topic'],'duration':5,'status':'awaiting_scene_plan',
             'engine':'lottie','revision':1,'scenePlan':plan}
        with tempfile.TemporaryDirectory() as temp,patch.object(vd,'JOB_DIR',Path(temp)),patch.object(vd,'JOBS',{'abc':job}):
            with self.assertRaisesRegex(ValueError,'Opuscar'):
                vd.update_job_plan('abc',{'stage':'scene_plan','revision':1,'scenePlan':self.plan({'camera':'locked'})})
            self.assertEqual(vd.JOBS['abc']['scenePlan'],plan)

    @unittest.skipUnless(shutil.which('node'),'Node unavailable')
    def test_three_absolute_controls_reset_after_reverse_seeks_and_gaps(self):
        program='''
const camera={position:{set(x,y,z){this.x=x;this.y=y;this.z=z}}};
const ambientLight={},keyLight={},rimLight={};
const shotControls=[{start:0,end:4,controls:{camera:'push-in',strength:1,lighting:'dramatic'}},
{start:4,end:8,controls:{camera:'locked',lighting:'soft'}}];
'''+scene_render.THREE_SCRIPT+'''
function sample(t){applySceneControls(t);return [camera.position.x,camera.position.y,camera.position.z,
ambientLight.intensity,keyLight.intensity,rimLight.intensity]}
console.log(JSON.stringify([sample(2),sample(6),sample(2),sample(9)]));'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,check=True,timeout=10)
        first,locked,repeated,gap=json.loads(result.stdout)
        self.assertEqual(first,repeated)
        self.assertEqual(first,[0,0,13.5,.5,6,7])
        self.assertEqual(locked,[0,0,15,3,2,2])
        self.assertEqual(gap[2:],[15,2,4,5])


class EvidenceDiagnosticsTests(unittest.TestCase):
    def test_compound_citations_are_not_mistaken_for_claim_numbers(self):
        article={'references':['First','Second','Third'],'blocks':[{'type':'p','text':'Ada 10 laporan [1, 2; 9].'}]}
        report=evidence.audit(article)
        self.assertEqual(report['claims'][0]['citations'],['1','2','9'])
        self.assertEqual(report['claims'][0]['unknown_citations'],['9'])
        self.assertEqual(report['claims'][0]['numbers_absent_from_excerpts'],['10'])
        self.assertEqual(report['diagnostics']['uncited_references'],[3])

    def test_attestation_does_not_hide_unsupported_numbers(self):
        article={'references':['Report'],'blocks':[{'type':'p','text':'Hasilnya 25% pada 2026 [1].'}]}
        claim=evidence.claims(article)[0]
        ledger={'sources':[{'id':'source','excerpt':'Hasilnya 20% pada 2026','verified':True}],
                'links':{claim['id']:['source']}}
        report=evidence.audit(article,ledger)
        self.assertEqual(report['unreviewed'],0)
        self.assertEqual(report['claims'][0]['numbers_absent_from_excerpts'],['25%'])
        self.assertEqual(report['diagnostics']['claims_with_warnings'],1)
        self.assertEqual(ledger['sources'][0]['excerpt'],'Hasilnya 20% pada 2026')

    def test_duplicate_bibliography_and_literal_limits(self):
        article={'references':['Same Report',' same   report '],'blocks':[{'type':'p','text':'Sebesar -3,5 % [01].'}]}
        report=evidence.audit(article)
        self.assertEqual(report['diagnostics']['duplicate_reference_groups'],[[1,2]])
        self.assertEqual(report['claims'][0]['unknown_citations'],[])
        self.assertEqual(report['claims'][0]['numbers_absent_from_excerpts'],['-3,5%'])
        huge=evidence.audit({'blocks':[{'type':'p','text':'['+'9'*5000+']'}]})
        self.assertEqual(len(huge['claims'][0]['unknown_citations'][0]),5000)


if __name__=='__main__':unittest.main()
