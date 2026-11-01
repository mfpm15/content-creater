import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import security
import video_job_store
import youtube_analytics


class HardeningTest(unittest.TestCase):
    def test_percentage_does_not_change_units_at_one_percent(self):
        for values in ('100%,2%,1%', '100,2,1'):
            csv = 'time,retention\n' + '\n'.join(f'{i},{v}' for i, v in enumerate(values.split(',')))
            self.assertEqual([p['retention'] for p in youtube_analytics.analyze_retention(csv.encode())['points']], [100, 2, 1])

    def test_fraction_column(self):
        data = b'time,ratio\n0,1\n1,0.5\n2,0.01\n'
        self.assertEqual([p['retention'] for p in youtube_analytics.analyze_retention(data)['points']], [100, 50, 1])

    def test_secrets_removed_from_error_and_checkpoint(self):
        with patch.dict(os.environ, {'LLM_API_KEY': 'example-secret-123'}):
            self.assertNotIn('example-secret-123', security.redact('Bearer example-secret-123'))
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                key = 'a' * 32
                video_job_store.save_job(directory, {'jobId': key, 'status': 'rendering', 'error': 'example-secret-123'})
                saved = json.loads((directory / (key + '.json')).read_text())
                self.assertNotIn('example-secret-123', saved['error'])
                self.assertEqual(video_job_store.recover_jobs(directory)[key]['status'], 'interrupted')
                self.assertEqual((directory / (key + '.json')).stat().st_mode & 0o777, 0o600)

    def test_provider_credentials_require_tls_and_no_url_userinfo(self):
        import urllib.request
        for url in ('http://example.com/v1', 'https://user:password@example.com/v1', 'https://example.com/v1?key=x'):
            with self.assertRaises(ValueError):
                security.open_authenticated(urllib.request.Request(url), 1)
