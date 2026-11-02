import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import animation_clock
import continuous_motion
from runtime_config import find_browser
import video_drafter as vd


FAKE = '''class Timeline {
 constructor(){this.t=0}
 duration(){return 10}
 time(){return this.t}
 pause(){return this}
 render(t){this.t=t;document.querySelector('#scene').style.display=t>=2?'block':'none';return this}
 totalTime(...args){if(!args.length)return this.t;return this.render(args[0])}
 seek(t){return this.totalTime(t,true)}
}
const tl=new Timeline();
attachAnimationClock(tl,t=>document.querySelector('#sample').dataset.time=t,8);
window.__timelines={video:tl};'''


class AnimationClockTests(unittest.TestCase):
    def test_templates_expose_both_adapter_contracts_and_seed_3d(self):
        plan=vd.normalize_scene_plan({},'Clock test','Narasi.',5)
        for engine in ('opuscar','threejs'):
            document=vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'],engine=engine)
            self.assertIn('attachAnimationClock(tl',document)
            self.assertIn('window.render = window.__seek',document)
            self.assertIn('window.__timelines.video = tl',document)
        three=vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'],engine='threejs')
        self.assertIn('preserveDrawingBuffer: true',three)
        self.assertNotIn('Math.random()',three)
        self.assertEqual(three,vd.generate_composition(plan,vd.ASPECT_RATIOS['9:16'],engine='threejs'))

    def test_remotion_catalog_describes_the_existing_separate_integration(self):
        data=json.loads((Path(__file__).parent/'tools.json').read_text())
        row=next(row for row in data['tools'] if row['id']=='remotion-studio')
        self.assertTrue(row['hidden'])
        self.assertIn('OpenCreator',row['description'])
        self.assertNotIn('Interactive Drag & Drop',row['capabilities'])

    def test_suppressed_and_parent_seeks_control_real_css_without_wall_time_drift(self):
        if not find_browser() or importlib.util.find_spec('playwright') is None:
            self.skipTest('Optional browser unavailable')
        from playwright.sync_api import sync_playwright
        html='''<style>body{margin:0}#scene{position:absolute;inset:0}#sample{width:40px;height:40px;background:red;
        animation:travel 4s linear infinite}#sample:before{content:"";display:block;width:8px;height:8px;background:blue;animation:travel 4s linear infinite}
        @keyframes travel{from{transform:translateX(0)}to{transform:translateX(160px)}}
        </style><div id="scene" data-start="2"><div id="sample"></div></div><script>'''+animation_clock.SCRIPT+FAKE+'</script>'
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'index.html';source.write_text(html)
            with continuous_motion._serve(source) as url, sync_playwright() as manager:
                browser=manager.chromium.launch(executable_path=find_browser(),chromium_sandbox=False)
                try:
                    page=browser.new_page(viewport={'width':320,'height':180})
                    page.goto(url);page.evaluate('async()=>{await window.__ready}')
                    self.assertTrue(page.evaluate('window.READY'))
                    self.assertEqual(page.evaluate('window.DUR'),8)
                    self.assertTrue(page.evaluate('()=>window.__timelines.video.seek(3,true)===window.__timelines.video'))
                    self.assertEqual(page.locator('#sample').get_attribute('data-time'),'3')
                    times=page.evaluate('()=>document.getAnimations().map(a=>[a.playState,a.currentTime])')
                    self.assertTrue(times)
                    self.assertTrue(all(state=='paused' and value==1000 for state,value in times),times)
                    first=page.screenshot()
                    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                    self.assertEqual(first,page.screenshot())
                    page.evaluate('window.render(1)')
                    page.evaluate('window.render(3)')
                    self.assertEqual(first,page.screenshot())
                    page.evaluate('window.__timelines.video.render(4,true,true)')
                    self.assertEqual(page.locator('#sample').get_attribute('data-time'),'4')
                    self.assertNotEqual(first,page.screenshot())
                    self.assertEqual(page.evaluate('window.__timelines.video.totalTime()'),4)
                    self.assertTrue(page.evaluate('window.render(99)'))
                    self.assertEqual(page.evaluate('window.__timelines.video.totalTime()'),8)
                    page.close()
                finally:browser.close()
