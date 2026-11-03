"""Regression checks for truthful metrics and non-overlapping Opuscar copy."""
import importlib.util
import os
from pathlib import Path
import unittest

import video_drafter as vd
from runtime_config import find_browser


class OpuscarLayoutTests(unittest.TestCase):
    def plan(self, title='Perubahan -3,5%', narration='Hasil pengukuran turun -3,5%.'):
        return vd.normalize_scene_plan({'scenes': [{
            'start': 0, 'end': 5, 'type': 'data', 'visualFamily': 'data',
            'onScreenText': title, 'narration': narration,
        }]}, 'Pengukuran', '', 5)

    def test_metrics_preserve_sign_and_do_not_invent_a_trend(self):
        for title, expected in [('Turun -3,5%', '-3,5%'), ('Naik +2.75%', '+2.75%'),
                                ('Turun −12%', '−12%'), ('Total 1.250,75', '1.250,75')]:
            with self.subTest(title=title):
                markup = vd._visual_markup(self.plan(title)['scenes'][0], 0)
                self.assertIn(f'<span class="num">{expected}</span>', markup)
                self.assertNotIn('bar-fill', markup)
                self.assertNotIn('trend-spline', markup)
        markup = vd._visual_markup(self.plan('Ringkasan', 'Biaya Rp1.250,75')['scenes'][0], 0)
        self.assertIn('<span class="num"></span>', markup)
        markup = vd._visual_markup(self.plan('Ringkasan', 'Turun -12%')['scenes'][0], 0)
        self.assertIn('<span class="num">-12%</span>', markup)

    def test_no_global_radar_decoration(self):
        document = vd.generate_composition(self.plan(), vd.ASPECT_RATIOS['9:16'])
        for token in ('scene-orbit', 'orbit-a', 'orbit-b', 'bg-grid', 'scanner-line',
                      'ambientOrbit', 'radar-ring', 'radar-sweep', 'panelPulse'):
            self.assertNotIn(token, document)

    def test_browser_text_fits_without_overlapping_hero_and_repeat_seek_is_stable(self):
        sdk = Path(os.environ.get('GSAP_TEST_SCRIPT', '/nonexistent'))
        if not sdk.is_file() or not find_browser() or importlib.util.find_spec('playwright') is None:
            self.skipTest('Requires optional browser/Playwright and GSAP_TEST_SCRIPT (GSAP 3.13.0)')
        from playwright.sync_api import sync_playwright
        script = sdk.read_text()
        self.assertIn('GSAP 3.13.0', script[:1000])
        title = 'MENJAGA KEAMANAN SISTEM DAN MEMUTUS RANTAI SERANGAN DENGAN PERTAHANAN BERLAPIS'
        narration = 'Setiap tahapan diperiksa agar tim dapat menemukan perubahan, melindungi data, dan menghentikan serangan sebelum berdampak pada layanan.'
        with sync_playwright() as manager:
            browser = manager.chromium.launch(executable_path=find_browser(), chromium_sandbox=False)
            try:
                for width, height in ((1080,1920), (1920,1080), (1080,1080), (1080,1350), (320,568)):
                    with self.subTest(size=(width,height)):
                        page = browser.new_page(viewport={'width':width,'height':height})
                        page.route('**/*', lambda route: route.fulfill(body=script, content_type='text/javascript')
                                   if route.request.url == 'https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js'
                                   else route.abort())
                        errors=[]
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.set_content(vd.generate_composition(self.plan(title,narration), {'width':width,'height':height}))
                        page.evaluate('async()=>{await window.__ready; window.__seek(2.5)}')
                        boxes=page.evaluate('''()=>{
                          const get=s=>{const e=document.querySelector(s),r=e.getBoundingClientRect();
                            return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,
                            overflow:e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2}};
                          return {title:get('.hero-title'),hero:get('.visual-wrapper'),caption:get('.subtitle-capsule')};
                        }''')
                        self.assertFalse(errors, errors)
                        for box in boxes.values():
                            self.assertFalse(box['overflow'], boxes)
                            self.assertGreaterEqual(box['left'], 0)
                            self.assertLessEqual(box['right'], width+1)
                            self.assertGreaterEqual(box['top'], 0)
                            self.assertLessEqual(box['bottom'], height+1)
                        self.assertLessEqual(boxes['title']['bottom'], boxes['hero']['top']+1, boxes)
                        self.assertLessEqual(boxes['hero']['bottom'], boxes['caption']['top']+1, boxes)
                        first=page.screenshot()
                        page.evaluate('window.__seek(4.5)')
                        page.evaluate('window.__seek(2.5)')
                        self.assertEqual(first, page.screenshot())
                        page.close()
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
