import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_drafter as vd
import video_job_store as store


class VideoRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.key = 'b' * 32
        self.job = {'jobId': self.key, 'topic': 'Contoh', 'duration': 15, 'revision': 3,
                    'status': 'awaiting_scene_plan', 'scenePlan': vd.normalize_scene_plan({}, 'Contoh', 'Narasi.', 15),
                    'storyboard': None, 'approvals': {}}
        self.patches = [patch.object(vd, 'JOBS', {self.key: self.job}), patch.object(vd, 'JOB_DIR', self.directory)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_stale_approval_and_edit_leave_checkpoint_unchanged(self):
        for action in (lambda: vd.approve_job(self.key, 'scene_plan', 2),
                       lambda: vd.update_job_plan(self.key, {'stage': 'scene_plan', 'revision': 2, 'scenePlan': self.job['scenePlan']})):
            with self.assertRaises(vd.RevisionConflict):
                action()
        self.assertEqual(self.job['status'], 'awaiting_scene_plan')
        self.assertFalse(list(self.directory.iterdir()))

    def test_duplicate_approve_starts_only_one_worker(self):
        with patch.object(vd.threading, 'Thread') as thread:
            vd.approve_job(self.key, 'scene_plan', 3)
            with self.assertRaises(ValueError):
                vd.approve_job(self.key, 'scene_plan', 3)
            thread.assert_called_once()
        self.assertEqual(self.job['approvals']['scene_plan'], 3)

    def test_resume_interrupted_plan_requires_approval_again(self):
        self.job.update(status='interrupted', approvals={'storyboard': 3})
        with patch.object(vd.threading, 'Thread') as thread:
            result = vd.resume_job(self.key, 3)
            thread.assert_not_called()
        self.assertEqual(result['status'], 'awaiting_scene_plan')
        self.assertEqual(result['revision'], 4)
        self.assertEqual(result['approvals'], {})
        self.assertEqual(store.recover_jobs(self.directory)[self.key]['status'], 'awaiting_scene_plan')

    def test_status_result_is_not_a_mutable_alias(self):
        result = vd.job_status(self.key)
        result['scenePlan']['scenes'][0]['narration'] = 'Mutated'
        self.assertNotEqual(result['scenePlan'], self.job['scenePlan'])

    def test_checkpoint_redaction_keeps_json_valid_and_private(self):
        secret = 'quote"\\secret-value'
        with patch.dict(os.environ, {'LLM_API_KEY': secret}):
            self.job['error'] = 'Provider: ' + secret
            store.save_job(self.directory, self.job)
        path = self.directory / (self.key + '.json')
        saved = json.loads(path.read_text())
        self.assertNotIn(secret, saved['error'])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(self.directory.glob('*.tmp')))

    def test_skip_symlink_checkpoint_and_invalid_revision(self):
        outside = self.directory / 'outside'
        outside.write_text(json.dumps(self.job))
        (self.directory / (self.key + '.json')).symlink_to(outside)
        self.assertEqual(store.recover_jobs(self.directory), {})
        (self.directory / (self.key + '.json')).unlink()
        self.job['revision'] = 'bad'
        store.save_job(self.directory, self.job)
        self.assertEqual(store.recover_jobs(self.directory), {})

    def test_edit_storyboard_invalidates_earlier_approval(self):
        self.job.update(status='awaiting_storyboard', approvals={'scene_plan': 3})
        plan = copy.deepcopy(self.job['scenePlan'])
        plan['scenes'][0]['narration'] = 'Diperbarui.'
        result = vd.update_job_plan(self.key, {'stage': 'storyboard', 'revision': 3, 'scenePlan': plan})
        self.assertEqual(result['status'], 'awaiting_scene_plan')
        self.assertEqual(result['revision'], 4)
        self.assertEqual(result['approvals'], {})

    def test_http_resume_and_revision_conflicts(self):
        import threading
        import urllib.error
        import urllib.request
        import server

        self.job['status'] = 'interrupted'
        httpd = server.ReusableThreadingHTTPServer(('127.0.0.1', 0), server.DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{httpd.server_port}'
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, payload=None, origin=None):
            headers = {'Content-Type': 'application/json'}
            if origin:
                headers['Origin'] = origin
            req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            try:
                with client.open(req, timeout=5) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                error.read()
                return error.code, None

        try:
            code, result = request('/api/videos/jobs')
            self.assertEqual(code, 200)
            self.assertEqual(result['jobs'][0]['jobId'], self.key)
            route = '/api/videos/jobs/' + self.key
            self.assertEqual(request(route + '/resume', {})[0], 400)
            self.assertEqual(request(route + '/resume', [1, 2])[0], 400)
            self.assertEqual(request(route + '/resume', {'revision': 2})[0], 409)
            code, job = request(route + '/resume', {'revision': 3})
            self.assertEqual(code, 200)
            self.assertEqual(job['status'], 'awaiting_scene_plan')
            self.assertEqual(request(route + '/approve', {'stage': 'scene_plan', 'revision': 3})[0], 409)
            self.assertEqual(request(route + '/approve', {'stage': 'scene_plan', 'revision': 4}, 'https://example.invalid')[0], 403)
            self.assertEqual(self.job['status'], 'awaiting_scene_plan')
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
            httpd.server_close()

    def test_unchanged_storyboard_save_preserves_approved_revision(self):
        self.job.update(status='awaiting_storyboard', approvals={'scene_plan': 3})
        result = vd.update_job_plan(self.key, {'stage': 'storyboard', 'revision': 3, 'scenePlan': copy.deepcopy(self.job['scenePlan'])})
        self.assertEqual(result['status'], 'awaiting_storyboard')
        self.assertEqual(result['approvals']['scene_plan'], 3)
        self.assertEqual(result['revision'], 3)
