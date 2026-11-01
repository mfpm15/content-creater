import hashlib
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import server
import video_bundle as bundle
import video_drafter as vd


class ProductionBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'lottie.json').write_text('{"layers":[]}')
    def tearDown(self):self.temp.cleanup()

    def test_only_explicit_artifacts_exported_and_checksums_match_redacted_bytes(self):
        secret='synthetic"\\api-key'
        original=json.dumps({'note':secret,'api_key':'unknown-private-value'})
        (self.root/'research.json').write_text(original)
        (self.root/'metadata.json').write_text('{"path":"private-directory"}')
        (self.root/'.env').write_text('private')
        (self.root/'review.json').write_text('{"status":"needs_attention"}')
        with patch.dict(os.environ,{'VIDEO_LLM_API_KEY':secret}),bundle.build(self.root) as path:
            with zipfile.ZipFile(path) as archive:
                names=set(archive.namelist())
                self.assertEqual(names,{'lottie.json','research.json','review.json','README.txt','manifest.json'})
                data=json.loads(archive.read('research.json'))
                self.assertNotIn(secret,data['note']);self.assertEqual(data['api_key'],'[REDACTED]')
                manifest=json.loads(archive.read('manifest.json'))
                self.assertEqual(manifest['review_status'],'needs_attention');self.assertTrue(manifest['manual_review_required'])
                for row in manifest['files']:
                    content=archive.read(row['file'])
                    self.assertEqual(row['sha256'],hashlib.sha256(content).hexdigest());self.assertEqual(row['bytes'],len(content))
        self.assertFalse(path.exists());self.assertEqual((self.root/'research.json').read_text(),original)

    def test_large_or_missing_result_fails_without_partial_archives(self):
        with patch.object(bundle,'MAX_BYTES',1),self.assertRaises(ValueError):
            with bundle.build(self.root):pass
        (self.root/'lottie.json').unlink()
        with self.assertRaises(ValueError):
            with bundle.build(self.root):pass
        self.assertFalse(list(self.root.glob('.handoff-*')))

    def test_parallel_export_rejects_busy_then_releases_slot(self):
        bundle.GATE.acquire()
        try:
            with self.assertRaises(bundle.BundleBusy):
                with bundle.build(self.root):pass
        finally:bundle.GATE.release()
        with bundle.build(self.root) as path:
            with bundle.build(self.root) as other:
                self.assertNotEqual(path,other);self.assertTrue(path.is_file());self.assertTrue(other.is_file())

    def test_linked_artifact_is_rejected_even_without_posix_nofollow(self):
        with patch.object(bundle,'_linked',side_effect=lambda path:path.name=='lottie.json'),self.assertRaises(ValueError):
            with bundle.build(self.root):pass

    def test_binary_video_is_preserved_without_expensive_zip_recompression(self):
        data=b'\x00'*1048576
        (self.root/'video.mp4').write_bytes(data)
        (self.root/'final-audio.wav').write_bytes(b'synthetic-audio')
        (self.root/'review.json').write_text(json.dumps({'status':'passed_media_checks','artifact_sha256':hashlib.sha256(data).hexdigest()}))
        with bundle.build(self.root) as path:
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read('video.mp4'),data)
                self.assertEqual(archive.read('final-audio.wav'),b'synthetic-audio')
                self.assertEqual(archive.getinfo('video.mp4').compress_type,zipfile.ZIP_STORED)
                self.assertEqual(json.loads(archive.read('manifest.json'))['review_binding'],'matches_exported_media')
        (self.root/'video.mp4').write_bytes(b'modified')
        with bundle.build(self.root) as path:
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(json.loads(archive.read('manifest.json'))['review_status'],'stale_review')

    def test_malformed_json_cleans_up_and_releases_slot(self):
        (self.root/'research.json').write_text('{invalid')
        with self.assertRaises(ValueError):
            with bundle.build(self.root):pass
        self.assertFalse(list(self.root.glob('.handoff-*')))
        (self.root/'research.json').unlink()
        with bundle.build(self.root) as path:self.assertTrue(path.is_file())

    def test_http_download_is_an_attachment_and_streams_a_valid_archive(self):
        (self.root/'metadata.json').write_text('{"engine":"lottie","topic":"Synthetic"}')
        httpd=server.ReusableThreadingHTTPServer(('127.0.0.1',0),server.DashboardHandler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            with patch.object(vd,'_video_directory',return_value=self.root):
                client=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=10)
                try:
                    client.request('GET','/api/videos/example/bundle');response=client.getresponse();data=response.read()
                    self.assertEqual(response.status,200);self.assertEqual(response.getheader('Content-Type'),'application/zip')
                    self.assertIn('attachment',response.getheader('Content-Disposition'))
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:self.assertIn('lottie.json',archive.namelist())
                finally:client.close()
        finally:httpd.shutdown();thread.join(5);httpd.server_close()
