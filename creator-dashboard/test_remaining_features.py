import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import analytics_import as imports
import analytics_learning as learning
import article_drafter as ad
import article_tools as tools
import evidence
import lottie_adapter
import video_drafter as vd
import source_reader


class RemainingFeatureTests(unittest.TestCase):
    def test_sources_reject_secrets_private_hosts_and_redirects(self):
        for url in ['http://example.org','https://name:password@example.org',
                    'https://example.org/?%61pi_key=placeholder','https://example.org/#token']:
            with self.assertRaises(ValueError):evidence.safe_url(url)
        with patch.dict('os.environ',{'RESEARCH_SOURCE_HOSTS':'example.org'}),patch.object(source_reader.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):source_reader.retrieve('https://example.org')
        with patch.dict('os.environ',{'RESEARCH_SOURCE_HOSTS':''}):
            with self.assertRaises(ValueError):source_reader.retrieve('https://example.org')
    def test_user_mapping_never_guesses_platform_columns(self):
        csv='Video;Tayang;Selesai\nv1;120;20\n'
        result=imports.mapped_import(csv,'reels',{'video_id':'Video','views':'Tayang','completion_percent':'Selesai'})
        self.assertEqual(result['records'][0]['views'],120)
        self.assertIn('unverified',result['schema'])
        with self.assertRaises(ValueError):imports.mapped_import(csv,'tiktok',{'views':'guessed'})

    def test_scene_mapping_and_missing_samples_are_explicit(self):
        result=imports.scene_retention([{'second':0,'retention':100}],[{'second':0,'kind':'cliff'}],
                                      [{'id':'a','start':0,'end':1},{'id':'b','start':1,'end':2}])
        self.assertIsNone(result[1]['average_sample_retention'])
        with self.assertRaises(ValueError):imports.scene_retention([],[],[{'start':1,'end':0}])

    def test_learning_requires_revision_and_has_no_publishing_action(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(learning,'ROOT',Path(tmp)):
            row=learning.create({'platform':'tiktok','video_id':'abc','window':'24h','metrics':{'views':100,'completion_percent':20}})
            self.assertEqual(row['status'],'proposed')
            decision=learning.decide(row['id'],1,True)
            self.assertEqual(decision['status'],'approved_experiment')
            with self.assertRaises(ValueError):learning.decide(row['id'],1,True)
            self.assertEqual(len(learning.list_observations()),1)

    def test_evidence_requires_review_excerpt_and_known_date_for_news(self):
        article={'blocks':[{'type':'p','text':'NASA merilis 3 laporan [1].'}]}
        ledger={}
        evidence.update(ledger,{'action':'source','url':'https://example.org/report','title':'Report','excerpt':'3 reports','published_at':''})
        key=ledger['sources'][0]['id'];claim=evidence.claims(article)[0]['id']
        evidence.update(ledger,{'action':'link','claim_id':claim,'source_ids':[key]})
        self.assertEqual(evidence.audit(article,ledger)['unreviewed'],1)
        evidence.update(ledger,{'action':'verify','source_id':key,'note':'Sudah dibandingkan dengan sumber'})
        self.assertEqual(evidence.audit(article,ledger)['unreviewed'],0)
        self.assertEqual(evidence.audit(article,ledger,7)['unreviewed'],1)
        ledger['sources'][0]['published_at']=date.today().isoformat()
        self.assertEqual(evidence.audit(article,ledger,7)['unreviewed'],0)

    def test_lottie_preview_embeds_exact_export_and_no_executable_user_markup(self):
        plan=vd.normalize_scene_plan({},'Test','Narasi.',15)
        plan['scenes'][0]['onScreenText']='</script><script>alert(1)</script>'
        animation=lottie_adapter.build(plan,vd.ASPECT_RATIOS['4:5'])
        html=lottie_adapter.preview(animation)
        self.assertNotIn('</script><script>alert(1)',html)
        embedded=html.split('<script id="animation" type="application/json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(embedded),animation)

    def test_aspect_variants_reuse_plan_but_require_approval(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(vd,'JOBS',{}),patch.object(vd,'JOB_DIR',Path(tmp)),patch.object(vd,'get_video',return_value={'engine':'lottie','scenePlan':vd.normalize_scene_plan({},'Test','Narration.',15)}):
            jobs=vd.create_aspect_jobs('source',['1:1','4:5'])
            self.assertEqual(len(jobs),2)
            self.assertTrue(all(j['status']=='awaiting_scene_plan' and not j['approvals'] for j in jobs))
            jobs[0]['scenePlan']['scenes'][0]['narration']='changed'
            self.assertNotEqual(vd.JOBS[jobs[0]['jobId']]['scenePlan'],jobs[0]['scenePlan'])


class ArticleToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.directory=self.root/'example';self.directory.mkdir()
        self.patches=[patch.object(ad,'ARTICLES_DIR',self.root),patch.object(ad,'JOBS',{})]
        for item in self.patches:item.start()
        self.article={'title':'Contoh','lang':'Indonesia','type':'populer','summary':'Ringkasan','keywords':[],
                      'numbered':False,'abstract_heading':False,'toc':False,'blocks':[{'type':'h2','text':'Bagian'},{'type':'p','text':'NASA merilis 3 laporan [1].'}],
                      'images':[],'references':['Sumber'],'suggested_references':[]}
        ad._write_json(self.directory/'article.json',self.article)
        ad._write_json(self.directory/'input.json',{})
        ad._write_json(self.directory/'sections/00.json',{'blocks':self.article['blocks'][1:]})
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()
    def test_rewrite_preserves_facts_and_requires_explicit_approval(self):
        def fake(system,user,normalizer):return normalizer({'texts':['NASA menerbitkan 3 laporan [1].']})
        with patch.object(ad,'_ask_json',side_effect=fake):
            proposal=tools.propose_rewrite('example',{'article_revision':tools.digest(self.article),'section':0})
        self.assertEqual(ad._read_json(self.directory/'article.json'),self.article)
        self.assertEqual(tools.proposals('example')[0]['id'],proposal['id'])
        with self.assertRaises(ValueError):tools.apply_rewrite('example',{'proposal_id':proposal['id'],'approve':False})
        result=tools.apply_rewrite('example',{'proposal_id':proposal['id'],'approve':True})
        self.assertIn('menerbitkan',result['markdown'])
        self.assertTrue((self.directory/'revisions'/('before-'+proposal['id']+'.json')).exists())
        with self.assertRaises(ValueError):tools.apply_rewrite('example',{'proposal_id':proposal['id'],'approve':True})
    def test_changed_numbers_in_rewrite_are_rejected(self):
        def fake(system,user,normalizer):return normalizer({'texts':['NASA merilis 4 laporan [1].']})
        with patch.object(ad,'_ask_json',side_effect=fake),self.assertRaises(ValueError):
            tools.propose_rewrite('example',{'article_revision':tools.digest(self.article),'section':0})
    def test_diagram_is_escaped_and_embedded_in_word(self):
        result=tools.add_diagram('example',{'article_revision':tools.digest(self.article),'kind':'flow','labels':['Start','<script>unsafe</script>'],'title':'Diagram'})
        self.assertEqual(len(result['images']),1)
        svg=next((self.directory/'images').glob('*.svg')).read_text()
        self.assertNotIn('<script>',svg)
        with zipfile.ZipFile(self.directory/'article.docx') as archive:
            self.assertTrue(any(name.startswith('word/media/') for name in archive.namelist()))
