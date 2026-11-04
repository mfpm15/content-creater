"""Native Three.js geometry and random-access regression using pinned real SDKs."""
import os
from pathlib import Path
import unittest
import video_drafter as vd
from runtime_config import find_browser


def plan():
    return vd.normalize_scene_plan({'scenes':[
        {'start':i*2,'end':i*2+2,'subject':subject,'action':action,'onScreenText':title,
         'narration':'Bentuk bergerak sesuai isi adegan.','renderControls':{'camera':'locked'}}
        for i,(subject,action,title) in enumerate([('seven chain links','tension','Rantai saling terhubung'),
            ('vault','open','Membuka ruang terlindungi'),('seven weights balance scale','balance','Menyeimbangkan pertahanan')])]},'Native scenes','',6)


class ThreeScenesTests(unittest.TestCase):
    def test_subjects_are_data_and_decorative_global_scene_is_removed(self):
        p=plan();p['scenes'][0]['directionSubject']='</script><script>bad()</script>'
        document=vd.generate_composition(p,vd.ASPECT_RATIOS['9:16'],engine='threejs')
        self.assertNotIn('<script>bad()',document)
        for old in ('GridHelper','IcosahedronGeometry','seededStar'):self.assertNotIn(old,document)
        self.assertIn('createThreeShots',document)

    def test_real_geometry_transitions_and_repeat_frames(self):
        gsap=Path(os.environ.get('GSAP_TEST_SCRIPT','/nonexistent'))
        three=Path(os.environ.get('THREE_TEST_SCRIPT','/nonexistent'))
        if not gsap.is_file() or not three.is_file() or not find_browser():self.skipTest('Requires pinned real GSAP/Three SDKs and Chromium')
        from playwright.sync_api import sync_playwright
        with sync_playwright() as manager:
            browser=manager.chromium.launch(executable_path=find_browser(),chromium_sandbox=False,
                args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            try:
                for w,h in ((1080,1920),(1920,1080),(1080,1080),(320,568)):
                    with self.subTest(size=(w,h)):
                        page=browser.new_page(viewport={'width':w,'height':h});errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.route('**/*',lambda r:r.fulfill(body=(gsap if 'gsap@' in r.request.url else three).read_text(),content_type='text/javascript'))
                        page.set_content(vd.generate_composition(plan(),{'width':w,'height':h},engine='threejs'))
                        page.evaluate('async()=>{await window.__ready}')
                        self.assertEqual(page.evaluate('window.__threeShots.map(s=>s.userData.kind)'),['chain','vault','balance'])
                        frames=[]
                        for t in (1,3,5):
                            page.evaluate('(t)=>window.__seek(t)',t);frames.append(page.screenshot())
                            boxes=page.evaluate("""()=>{
                              const group=window.__threeShots.find(s=>s.visible),b=new THREE.Box3().setFromObject(group),points=[];
                              for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z]){
                                const p=new THREE.Vector3(x,y,z).project(camera);points.push([(p.x+1)*width/2,(1-p.y)*height/2]);
                              }
                              const section=[...document.querySelectorAll('.scene-hud')].find(e=>getComputedStyle(e).display!=='none');
                              const title=section.querySelector('.hero-title').getBoundingClientRect(),caption=section.querySelector('.subtitle-capsule').getBoundingClientRect();
                              return {left:Math.min(...points.map(p=>p[0])),right:Math.max(...points.map(p=>p[0])),top:Math.min(...points.map(p=>p[1])),bottom:Math.max(...points.map(p=>p[1])),titleBottom:title.bottom,captionTop:caption.top};
                            }""")
                            self.assertGreaterEqual(boxes['left'],0,boxes);self.assertLessEqual(boxes['right'],w,boxes)
                            self.assertLessEqual(boxes['titleBottom'],boxes['top'],boxes)
                            self.assertLessEqual(boxes['bottom'],boxes['captionTop'],boxes)
                            page.evaluate('window.__seek(.2)');page.evaluate('(t)=>window.__seek(t)',t)
                            self.assertEqual(frames[-1],page.screenshot())
                        self.assertEqual(len(set(frames)),3)
                        for t in (0,2,4):
                            page.evaluate('(t)=>window.__seek(t)',t)
                            self.assertTrue(page.evaluate('window.__threeShots.some(s=>s.visible && s.children.some(o=>o.isMesh?o.material.opacity>0:o.children.some(m=>m.material?.opacity>0)))'))
                        self.assertFalse(errors,errors);page.close()
            finally:browser.close()
