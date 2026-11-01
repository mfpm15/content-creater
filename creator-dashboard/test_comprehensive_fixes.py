import http.client
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

import article_drafter as ad
import article_storage as storage
import article_tools as tools
import security
import server
import video_drafter as vd
import video_review
import test_remaining_features as fixtures


class RequestSecurityTests(unittest.TestCase):
    def setUp(self):
        self.http=server.ReusableThreadingHTTPServer(('127.0.0.1',0),server.DashboardHandler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.host=f'127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown();self.thread.join(5);self.http.server_close()

    def request(self,method,path,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            connection.request(method,path,headers=headers or {})
            response=connection.getresponse();return response.status,dict(response.headers),response.read()
        finally:connection.close()

    def test_exact_origin_and_cross_site_are_enforced(self):
        for origin in [f'https://{self.host}',f'ftp://{self.host}',f'http://{self.host}/path','null']:
            self.assertEqual(self.request('GET','/api/videos/jobs',{'Origin':origin})[0],403)
        self.assertEqual(self.request('GET','/api/videos/jobs',{'Origin':'http://'+self.host})[0],200)
        self.assertEqual(self.request('POST','/api/tools/unknown/start',{'Sec-Fetch-Site':'cross-site'})[0],403)

    def test_json_redacts_secrets_before_encoding_and_head_has_no_body(self):
        secret='quoted"\\credential-value'
        with patch.dict(os.environ,{'LLM_API_KEY':secret}),patch.object(server.video_drafter,'list_jobs',return_value=[{'error':secret}]):
            status,headers,body=self.request('GET','/api/videos/jobs')
            self.assertEqual(status,200);self.assertNotIn(secret,json.loads(body)['jobs'][0]['error'])
            status,head_headers,body=self.request('HEAD','/api/videos/jobs')
            self.assertEqual(status,200);self.assertEqual(body,b'')
            self.assertEqual(headers['Content-Length'],head_headers['Content-Length'])

    def test_duplicate_body_length_and_transfer_encoding_are_rejected(self):
        for headers in [[('Content-Length','0'),('Content-Length','0')],[('Transfer-Encoding','chunked')]]:
            connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
            try:
                connection.putrequest('POST','/api/videos')
                for key,value in headers:connection.putheader(key,value)
                connection.endheaders();response=connection.getresponse();response.read()
                self.assertEqual(response.status,400)
            finally:connection.close()

    def test_video_streams_byte_ranges_without_reading_entire_file(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(vd,'VIDEOS_DIR',Path(tmp)),patch.object(vd,'read_video_file',side_effect=AssertionError('Must stream')):
            folder=Path(tmp)/'example';folder.mkdir();(folder/'video.mp4').write_bytes(b'0123456789')
            route='/api/videos/example/video.mp4'
            for value,expected in [('bytes=2-5',b'2345'),('bytes=-3',b'789'),('bytes=7-',b'789')]:
                status,headers,body=self.request('GET',route,{'Range':value})
                self.assertEqual(status,206);self.assertEqual(body,expected);self.assertEqual(int(headers['Content-Length']),len(expected))
            self.assertEqual(self.request('HEAD',route,{'Range':'bytes=0-3'})[2],b'')
            for value in ['bytes=20-','bytes=0-1,3-4','bytes=-0']:
                self.assertEqual(self.request('GET',route,{'Range':value})[0],416)
            outside=Path(tmp)/'outside.mp4';outside.write_bytes(b'private')
            (folder/'video.mp4').unlink();(folder/'video.mp4').symlink_to(outside)
            self.assertEqual(self.request('GET',route)[0],404)

    def test_static_files_cannot_escape_or_list_private_directories(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'STATIC_DIR',Path(tmp)):
            root=Path(tmp);(root/'private').mkdir();(root/'private/data.txt').write_text('private')
            (root/'.env').write_text('private');(root/'public.txt').write_text('public')
            self.assertEqual(self.request('GET','/private/')[0],404)
            self.assertEqual(self.request('GET','/.env')[0],404)
            self.assertEqual(self.request('HEAD','/public.txt')[0],200)
            (root/'escape.txt').symlink_to('/etc/hostname')
            self.assertEqual(self.request('GET','/escape.txt')[0],404)


class ArticleTransactionTests(unittest.TestCase):
    setUp=fixtures.ArticleToolsTests.setUp
    tearDown=fixtures.ArticleToolsTests.tearDown
    def test_failed_docx_render_keeps_source_proposal_and_documents(self):
        ad.build_outputs('example')
        before={name:(self.directory/name).read_bytes() for name in ('article.json','sections/00.json','article.md','article.docx')}
        def fake(system,user,normalizer):return normalizer({'texts':['NASA menerbitkan 3 laporan [1].']})
        with patch.object(ad,'_ask_json',side_effect=fake):
            proposal=tools.propose_rewrite('example',{'article_revision':tools.digest(self.article),'section':0})
        with patch.object(ad,'to_docx',side_effect=OSError('Simulated disk failure')),self.assertRaises(OSError):
            tools.apply_rewrite('example',{'proposal_id':proposal['id'],'approve':True})
        for name,body in before.items():self.assertEqual((self.directory/name).read_bytes(),body)
        self.assertEqual(tools.proposals('example')[0]['status'],'proposed')
        self.assertFalse(list(self.directory.glob('.edit-*')))

    def test_interrupted_commit_is_rolled_back_on_next_read(self):
        stage=self.directory/'.edit-synthetic';(stage/'before').mkdir(parents=True)
        original=(self.directory/'article.json').read_bytes()
        storage.atomic_bytes(stage/'before/article.json',original)
        storage.atomic_bytes(self.directory/'article.json',b'{"title":"partial"}')
        storage.atomic_bytes(self.directory/'new.json',b'{}')
        storage.atomic_bytes(self.directory/storage.JOURNAL,storage.json_bytes({'stage':stage.name,'files':[
            {'name':'article.json','existed':True},{'name':'new.json','existed':False}]}))
        ad._dir('example')
        self.assertEqual((self.directory/'article.json').read_bytes(),original)
        self.assertFalse((self.directory/'new.json').exists())
        self.assertFalse(stage.exists())

    def test_mid_commit_failure_rolls_back_all_live_files(self):
        ad.build_outputs('example')
        original=(self.directory/'article.json').read_bytes()
        documents={name:(self.directory/name).read_bytes() for name in ('article.md','image-prompts.md','article.docx')}
        real=storage.atomic_bytes;failed=False
        def fail_once(path,data):
            nonlocal failed
            if path==self.directory/'article.docx' and not failed:
                failed=True;raise OSError('Simulated final replace failure')
            return real(path,data)
        with patch.object(storage,'atomic_bytes',side_effect=fail_once),self.assertRaises(OSError):
            storage.commit(self.directory,{'article.json':b'{}','new.json':b'{}'},self.article,ad._render_output_files)
        self.assertEqual((self.directory/'article.json').read_bytes(),original)
        self.assertFalse((self.directory/'new.json').exists())
        self.assertFalse((self.directory/storage.JOURNAL).exists())
        for name,body in documents.items():self.assertEqual((self.directory/name).read_bytes(),body)

    def test_locked_unchanged_docx_does_not_prevent_rollback(self):
        ad.build_outputs('example')
        original=(self.directory/'article.json').read_bytes();real=storage.atomic_bytes
        def locked(path,data):
            if path==self.directory/'article.docx':raise PermissionError('Word keeps the document open')
            return real(path,data)
        with patch.object(storage,'atomic_bytes',side_effect=locked),self.assertRaises(PermissionError):
            storage.commit(self.directory,{'article.json':b'{}'},self.article,ad._render_output_files)
        self.assertEqual((self.directory/'article.json').read_bytes(),original)
        self.assertFalse((self.directory/storage.JOURNAL).exists())


class OriginUnitTests(unittest.TestCase):
    def test_encoded_log_credentials_are_redacted_without_breaking_other_parameters(self):
        from urllib.parse import quote
        value='quoted"\\value-example'
        with patch.dict(os.environ,{'LLM_API_KEY':value}):
            self.assertNotIn(quote(value,safe=''),security.redact('failed '+quote(value,safe='')))
            self.assertNotIn(json.dumps(value)[1:-1],security.redact(json.dumps(value)))
        self.assertEqual(security.redact('https://example.org/?%61pi_key=private-value&title=example'),'https://example.org/?%61pi_key=[REDACTED]&title=example')
        self.assertEqual(security.redact('Basic dXNlcjpwYXNz'),'Basic [REDACTED]')
        self.assertEqual(security.redact('basic training'),'basic training')
    def test_renderer_does_not_inherit_application_credentials(self):
        with patch.dict(os.environ,{'VIDEO_LLM_API_KEY':'synthetic-key','CLIPPER_TOKEN':'synthetic-token','HTTPS_PROXY':'http://proxy:8080','SSL_CERT_FILE':'/tmp/test-ca.pem'}):
            environment=security.render_environment()
        self.assertNotIn('VIDEO_LLM_API_KEY',environment);self.assertNotIn('CLIPPER_TOKEN',environment)
        self.assertEqual(environment['HTTPS_PROXY'],'http://proxy:8080')
        self.assertEqual(environment['SSL_CERT_FILE'],'/tmp/test-ca.pem')
        self.assertEqual(environment['HYPERFRAMES_NO_TELEMETRY'],'1')
    def test_invalid_hosts_and_origin_credentials_are_never_local(self):
        for host in ['localhost:1@evil.invalid','localhost:123/path','localhost:123?x','localhost:123,evil','localhost:999']:
            self.assertFalse(security.local_request_allowed(host,None,123))
        self.assertFalse(security.local_request_allowed('localhost:123','http://user@localhost:123',123))


class VideoReliabilityTests(unittest.TestCase):
    def test_voice_failure_does_not_start_expensive_visual_render(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(vd,'VIDEOS_DIR',Path(tmp)/'videos'),patch.object(vd,'JOB_DIR',Path(tmp)/'jobs'),patch.object(vd,'JOBS',{}),patch.object(vd.threading,'Thread'):
            key=vd.start_job({'topic':'Test','script':'Naskah pengguna.','engine':'opuscar','researchMode':'provided'})['jobId']
            vd._run_job(key)
            with patch.object(vd,'runtime_issues',return_value=[]),patch.object(vd,'_build_audio',side_effect=RuntimeError('Voice unavailable')),patch.object(vd.subprocess,'run') as renderer:
                vd._continue_job(key,'storyboard')
            renderer.assert_not_called()
            self.assertEqual(vd.job_status(key)['status'],'failed')
            self.assertIn('Voice unavailable',vd.job_status(key)['error'])
    @unittest.skipUnless(shutil.which('chromium') and importlib.util.find_spec('playwright'),'Optional browser review dependencies unavailable')
    def test_visual_review_handles_timeline_methods_returning_cyclic_objects(self):
        import visual_review
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'VIDEO_REVIEW_ALLOW_NO_SANDBOX':'1'}):
            root=Path(tmp)
            (root/'index.html').write_text('<style>body{margin:0}.hero-title{width:2000px}</style><h1 class="hero-title">Overflow</h1><script>const t={pause(){return this},seek(){return this}};t.parent=t;t.window=window;window.__timelines={video:t};</script>')
            report=visual_review.inspect(root/'index.html',{'scenes':[{'id':'s1','start':0,'end':2}]},320,568)
            self.assertEqual(report['status'],'needs_attention',report)
            self.assertEqual(report['issues'][0]['code'],'text_overflow')
            self.assertTrue((root/'review-frame-0.png').is_file())
    def test_narration_only_lottie_pipeline_never_calls_external_providers(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(vd,'VIDEOS_DIR',Path(tmp)/'videos'),patch.object(vd,'JOB_DIR',Path(tmp)/'jobs'),patch.object(vd,'JOBS',{}),patch.object(vd.threading,'Thread'),patch.object(vd,'_research_web',side_effect=AssertionError('No web')),patch.object(vd,'_call_9router',side_effect=AssertionError('No LLM')):
            result=vd.start_job({'topic':'Lokal','script':'Narasi dari pengguna. Periksa fakta ini.','engine':'lottie','researchMode':'provided','duration':15})
            key=result['jobId'];vd._run_job(key)
            job=vd.job_status(key);self.assertEqual(job['status'],'awaiting_scene_plan');self.assertEqual(job['research']['mode'],'provided')
            vd.approve_job(key,'scene_plan',job['revision']);vd._continue_job(key,'scene_plan')
            job=vd.job_status(key);vd.approve_job(key,'storyboard',job['revision']);vd._continue_job(key,'storyboard')
            job=vd.job_status(key);self.assertEqual(job['status'],'succeeded')
            saved=vd.get_video(job['video']['slug']);self.assertTrue(saved['lottieUrl'])
            self.assertEqual(saved['scenePlan']['scenes'][0]['narration'],'Narasi dari pengguna.')

    def test_invalid_plans_are_rejected_before_render_work(self):
        for scenes in [[None],[{'start':0,'end':float('nan')}],[{'start':-1,'end':5}],[{'start':0,'end':601}],[{'start':0,'end':None}], [{}]*201]:
            with self.assertRaises(ValueError):vd.normalize_scene_plan({'scenes':scenes},'Test','',15)
        with self.assertRaises(ValueError):vd.start_job({'topic':'Test','researchMode':'provided'})

    def test_scene_kind_cannot_inject_markup_in_either_render_adapter(self):
        plan=vd.normalize_scene_plan({'scenes':[{'start':0,'end':2,'type':'<img src=x onerror=&#97;&#108;&#101;&#114;&#116;(1)>','narration':'Aman'}]},'Test','',2)
        for engine in ('opuscar','threejs'):
            document=vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'],engine=engine)
            self.assertNotIn('<IMG SRC=X',document)
            self.assertIn('&lt;IMG SRC=X',document)

    def test_audio_timeout_and_browser_failure_keep_review_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'index.html').write_text('test')
            probe={'format':{'duration':'2'},'streams':[{'codec_type':'video','width':320,'height':568},{'codec_type':'audio'}]}
            plan={'scenes':[{'id':'s1','start':0,'end':2,'narration':'Narasi'}]}
            with patch.object(video_review.shutil,'which',side_effect=lambda name:name),patch.object(video_review.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,json.dumps(probe).encode(),b''),subprocess.TimeoutExpired('ffmpeg',180)]),patch('visual_review.inspect',side_effect=OSError('Browser unavailable')):
                report=video_review.review(root/'video.mp4',2,plan)
            self.assertEqual(report['audio']['status'],'unmeasured');self.assertEqual(report['visual_review']['status'],'unmeasured')
            self.assertEqual(report['status'],'needs_attention');json.dumps(report,allow_nan=False)
