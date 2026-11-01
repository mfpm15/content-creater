import copy
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import creative_profile as profiles
import lottie_adapter
import server
import video_drafter as vd


class CreativeProfileTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        self.addCleanup(self.workspace.cleanup)
        for item in [patch.object(vd, 'JOBS', {}), patch.object(vd, 'JOB_DIR', self.root/'jobs'),
                     patch.object(vd, 'VIDEOS_DIR', self.root/'videos')]:
            item.start()
            self.addCleanup(item.stop)
        self.store = self.root/'brand-kits.json'
        self.raw = {'scenes': [{'start': 0, 'end': 5, 'narration': 'Tidak 3 kali',
                    'wordCues': [{'word': 'Tidak', 'start': 0, 'end': .4},
                                 {'word': '3', 'start': 1.25, 'end': 1.5},
                                 {'word': 'kali', 'start': 2, 'end': 2.4}], 'visualCueWord': 1}]}

    def plan(self, data=None):
        return vd.normalize_scene_plan(data or self.raw, 'Test', '', 5)

    def test_store_upsert_and_stale_revision_preserve_existing_snapshot(self):
        first = profiles.save(self.store, {'revision': 0, 'brand': {'name': ' Kopi ', 'accent': '#AA1122'}})
        snapshot = profiles.snapshot(first['kits'][0])
        second = profiles.save(self.store, {'revision': 1, 'brand': {'name': 'kopi', 'accent': '#123456'}})
        self.assertEqual(first['kits'][0]['id'], second['kits'][0]['id'])
        self.assertEqual(snapshot['accent'], '#aa1122')
        self.assertEqual(len(second['kits']), 1)
        with self.assertRaises(ValueError):
            profiles.save(self.store, {'revision': 1, 'brand': {'name': 'Old'}})
        self.assertEqual(profiles.catalog(self.store), second)

    def test_allowlist_rejects_css_urls_and_control_characters(self):
        for values in [{'accent': 'red;url(https://example.com)'}, {'font': '</style><script>'},
                       {'wordmark': 'A\nB'}, {'name': ' '}, {'text': '#fff'}, {'accent': 123}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                profiles.brand(values)
        kit = profiles.brand({'api_key': 'not-a-setting', 'logo': 'https://example.com'})
        self.assertNotIn('api_key', kit)
        self.assertNotIn('logo', kit)

    def test_store_rejects_linked_ancestors_and_oversized_data(self):
        with patch.object(Path, 'is_junction', return_value=True, create=True):
            with self.assertRaises(ValueError): profiles.catalog(self.store)
        self.store.write_bytes(b' '*100001)
        with self.assertRaises(ValueError): profiles.catalog(self.store)
        self.store.write_text('{"revision":0,"kits":[false]}')
        with self.assertRaises(ValueError): profiles.catalog(self.store)

    def test_timing_keeps_numbers_negation_and_exact_requested_time(self):
        scene = self.plan()['scenes'][0]
        self.assertEqual(profiles.reveal(scene), 1.25)
        for word in ('30', 'Bukan'):
            raw = copy.deepcopy(self.raw)
            raw['scenes'][0]['wordCues'][1]['word'] = word
            with self.assertRaises(ValueError): self.plan(raw)
        raw = copy.deepcopy(self.raw)
        raw['scenes'][0]['narration'] = 'Tidak 3.14 kali'
        raw['scenes'][0]['wordCues'][1]['word'] = '3 14'
        with self.assertRaises(ValueError): self.plan(raw)

    def test_invalid_word_times_and_indices_are_rejected(self):
        for field, value in [('start', -1), ('start', float('nan')), ('end', float('inf')),
                             ('end', 1000000000000000000000000000000), ('start', True), ('end', .1)]:
            raw = copy.deepcopy(self.raw)
            raw['scenes'][0]['wordCues'][1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): self.plan(raw)
        for index in (-1, 3, True, .5):
            raw = copy.deepcopy(self.raw)
            raw['scenes'][0]['visualCueWord'] = index
            with self.assertRaises(ValueError): self.plan(raw)
        raw = copy.deepcopy(self.raw)
        del raw['scenes'][0]['wordCues']
        with self.assertRaises(ValueError): self.plan(raw)

    def test_cues_can_be_cleared_and_legacy_plans_have_no_new_fields(self):
        raw = copy.deepcopy(self.raw)
        raw['scenes'][0].update(wordCues=[], visualCueWord=None)
        scene = self.plan(raw)['scenes'][0]
        self.assertNotIn('visualCueWord', scene)
        self.assertEqual(profiles.reveal(scene, .12), .12)
        legacy = vd.normalize_scene_plan({}, 'Test', 'Kalimat saja.', 5)
        self.assertNotIn('brand', legacy)
        self.assertNotIn('wordCues', legacy['scenes'][0])

    def test_brand_and_timing_reach_both_render_formats_without_executable_markup(self):
        raw = copy.deepcopy(self.raw)
        raw['brand'] = {'name': 'Kit', 'wordmark': '<img src=x>', 'accent': '#123456',
                        'background': '#223344', 'font': 'Georgia', 'text': '#ffeedd'}
        plan = self.plan(raw)
        for engine in ('opuscar', 'threejs'):
            html = vd.generate_composition(plan, vd.ASPECT_RATIOS['9:16'], engine=engine)
            self.assertIn('&lt;img src=x&gt;', html)
            self.assertNotIn('<img src=x>', html)
            self.assertIn('#stage{background:#223344}', html)
            self.assertIn('font-family:Georgia', html)
            self.assertIn('1.25);', html)
        animation = lottie_adapter.build(plan, vd.ASPECT_RATIOS['9:16'])
        shape = next(layer for layer in animation['layers'] if layer['nm'] == 'scene-1')
        self.assertEqual(shape['ip'], round(1.25*30))
        self.assertEqual(animation['layers'][-1]['nm'], 'brand-background')
        self.assertEqual(animation['layers'][0]['nm'], 'brand-wordmark')
        self.assertEqual(animation['fonts']['list'][0]['fFamily'], 'Georgia')
        for layer in animation['layers']:
            if layer['ty'] == 5:
                self.assertEqual(layer['t']['m']['g'], 1)
                self.assertEqual(layer['t']['m']['a']['k'], [0, 0])
        preview = lottie_adapter.preview(animation)
        self.assertNotIn('<img src=x>', preview)
        self.assertIn('data.layers].reverse()', preview)

    def test_short_cue_does_not_generate_nonmonotonic_lottie_keyframes(self):
        raw = {'scenes': [{'start': 0, 'end': 5, 'narration': 'Halo',
               'wordCues': [{'word': 'Halo', 'start': 4.99, 'end': 5}], 'visualCueWord': 0}]}
        animation = lottie_adapter.build(self.plan(raw), vd.ASPECT_RATIOS['1:1'])
        for layer in animation['layers']:
            times = [key['t'] for key in layer['ks']['o']['k']]
            self.assertEqual(times, sorted(times))
            self.assertLess(layer['ip'], layer['op'])

    def test_job_uses_snapshot_and_storyboard_edit_clears_approvals(self):
        data = profiles.save(self.store, {'revision': 0, 'brand': {'name': 'Kopi'}})
        with patch.object(vd.threading.Thread, 'start'):
            result = vd.start_job({'topic': 'Kopi', 'script': 'Tidak 3 kali', 'engine': 'lottie',
                                  'researchMode': 'provided', 'brandId': data['kits'][0]['id']})
        key = result['jobId']
        vd._run_job(key)
        job = vd.JOBS[key]
        plan = self.plan()
        plan['brand'] = job['scenePlan']['brand']
        job.update(status='awaiting_storyboard', approvals={'scene_plan': 0})
        updated = vd.update_job_plan(key, {'stage': 'storyboard', 'revision': job['revision'], 'scenePlan': plan})
        self.assertEqual(updated['status'], 'awaiting_scene_plan')
        self.assertEqual(updated['approvals'], {})
        profiles.save(self.store, {'revision': 1, 'brand': {'name': 'Kopi', 'accent': '#111111'}})
        self.assertEqual(updated['scenePlan']['brand']['accent'], '#22d3ee')

    def test_http_brand_routes_inherit_origin_protection(self):
        httpd = server.ReusableThreadingHTTPServer(('127.0.0.1', 0), server.DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, body=None, origin=None):
                client = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
                try:
                    headers = {'Content-Type': 'application/json'}
                    if origin: headers['Origin'] = origin
                    client.request(method, '/api/videos/brands', json.dumps(body) if body is not None else None, headers)
                    response = client.getresponse()
                    content = response.read()
                    return response.status, json.loads(content) if response.getheader('Content-Type', '').startswith('application/json') else {}
                finally: client.close()
            status, data = request('GET')
            self.assertEqual((status, data['revision']), (200, 0))
            payload = {'revision': 0, 'brand': {'name': 'Kit'}}
            self.assertEqual(request('POST', payload, 'https://evil.example')[0], 403)
            self.assertEqual(request('POST', payload)[0], 200)
            self.assertEqual(request('POST', payload)[0], 400)
            self.assertEqual(request('POST', [])[0], 400)
        finally:
            httpd.shutdown()
            thread.join(5)
            httpd.server_close()
