"""Isolated, bounded style-frame review before approving a mechanical storyboard."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

import opuscar_scene_spec
from security import render_environment


def digest(document: str) -> str:
    return hashlib.sha256(document.encode('utf-8')).hexdigest()


def required(plan: dict) -> bool:
    return bool(plan.get('scenes'))


def verify(document: str, report: dict | None) -> None:
    if not report or report.get('status')!='sampled' or report.get('issues') or report.get('digest')!=digest(document):
        raise ValueError('Review visual Opuscar belum lulus atau sudah berubah. Revisi dan setujui ulang Scene Plan untuk membuat style frames baru.')


def inspect(target: Path, plan: dict, aspect: dict) -> dict:
    """A missing browser, timeout or worker error never counts as a passing audit."""
    document=(target/'index.html').read_text(encoding='utf-8')
    report={'status':'unmeasured','digest':digest(document),'issues':[],'frames':[]}
    with tempfile.TemporaryDirectory(prefix='.opuscar-review-',dir=target) as folder:
        request=Path(folder)/'request.json'; response=Path(folder)/'response.json'
        request.write_text(json.dumps({'target':str(target.resolve()),'plan':plan,'aspect':aspect}),encoding='utf-8')
        request.chmod(0o600)
        kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(request),str(response)],
            env=render_environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kwargs)
        try:
            process.wait(timeout=120)
            if process.returncode or not response.is_file():
                report['issues']=[{'reason':'Isolated visual review failed; check browser/Playwright/Pillow runtime'}]
            else:
                report=json.loads(response.read_text(encoding='utf-8'))
        except subprocess.TimeoutExpired:
            report['issues']=[{'reason':'Visual review exceeded 120 seconds'}]
        finally:
            if process.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                else:os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=15)
    (target/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def compare_pixels(first, second) -> dict:
    """Allow only measured Chromium edge quantization, never geometric displacement."""
    from PIL import ImageChops
    difference=ImageChops.difference(first.convert('RGB'),second.convert('RGB'))
    r,g,b=difference.split()
    histogram=ImageChops.lighter(ImageChops.lighter(r,g),b).histogram()
    delta=max(i for i,count in enumerate(histogram) if count)
    fraction=sum(histogram[1:])/(first.width*first.height)
    return {'exact':delta==0,'maxChannelDelta':delta,'changedFraction':fraction,
            'withinTolerance':delta<=2 and fraction<=.01}


def _inspect(target: Path, plan: dict, aspect: dict) -> dict:
    from PIL import Image, ImageStat
    from playwright.sync_api import sync_playwright
    from continuous_motion import _serve
    from runtime_config import find_browser
    report=opuscar_scene_spec.audit(plan)
    document=(target/'index.html').read_text(encoding='utf-8')
    report.update(digest=digest(document),frames=[],observedFrames=0,repeatSamples=[],rasterTolerance={'maxChannelDelta':2,'maxChangedFraction':.01},method='mechanical_scene_phase_dom_and_pixels',
                  manualRequired='Story, aesthetics, semantics, sound and untested frames require review')
    width,height=aspect['width'],aspect['height']
    sdk_url='https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js'
    sdk_path=os.getenv('GSAP_TEST_SCRIPT')
    sdk=Path(sdk_path).read_text(encoding='utf-8') if sdk_path else None
    if sdk and 'GSAP 3.13.0' not in sdk[:1000]:raise ValueError('Review SDK must be GSAP 3.13.0')
    with _serve(target/'index.html') as url, sync_playwright() as manager:
        browser=manager.chromium.launch(executable_path=find_browser(),
            chromium_sandbox=os.getenv('VIDEO_REVIEW_ALLOW_NO_SANDBOX')!='1')
        try:
            page=browser.new_page(viewport={'width':width,'height':height},service_workers='block',accept_downloads=False)
            def route_request(route):
                address=route.request.url
                if address==sdk_url and sdk:route.fulfill(body=sdk,content_type='text/javascript')
                elif address in (url,sdk_url):route.continue_()
                else:route.abort()
            page.route('**/*',route_request)
            errors=[];page.on('pageerror',lambda _:errors.append('Browser drawing error'))
            page.goto(url,wait_until='load',timeout=20000)
            page.evaluate('async()=>{await window.__ready}')
            for index, scene in enumerate(plan['scenes']):
                # Every scene and every named action phase is examined, no first-20 truncation.
                for phase in (.15,.45,.75):
                    t=scene['start']+scene['duration']*phase
                    page.evaluate('async(t)=>{window.__seek(t); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}',t)
                    geometry=page.evaluate('''index=>{
                        const scene=document.querySelector('#sc_'+index);
                        const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
                        const texts=[...scene.querySelectorAll('.hero-title,.subtitle-capsule')];
                        const overflow=texts.some(e=>{const r=rect(e);return r.left<0||r.right>innerWidth+1||r.top<0||r.bottom>innerHeight+1||e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2});
                        const title=rect(texts[0]),caption=rect(texts[1]),visual=rect(scene.querySelector('.visual-wrapper'));
                        const hero=scene.querySelector('[data-part="hero"]');
                        return {unsupported:Boolean(scene.querySelector('[data-interpretation="unsupported"]')),overflow,overlap:title.bottom>visual.top+1||visual.bottom>caption.top+1,
                            tooSmall:texts.some(e=>parseFloat(getComputedStyle(e).fontSize)<14*Math.min(innerWidth,innerHeight)/1080),
                            hero:hero?rect(hero):null, layers:scene.querySelectorAll('.scene-background,.scene-midground,.scene-foreground').length};
                    }''',index)
                    report['observedFrames']+=1
                    for key in ('overflow','overlap','tooSmall','unsupported'):
                        if geometry[key]:report['issues'].append({'scene':index,'phase':phase,'reason':key})
                    if report['specs'][index]:
                        if geometry['layers']!=3:report['issues'].append({'scene':index,'reason':'Missing staging layers'})
                        hero=geometry['hero']
                        if not hero or hero['height']<height/3:
                            report['issues'].append({'scene':index,'phase':phase,'reason':'Hero occupies less than one third of frame height'})
                    if phase==.75:
                        before_dom=page.locator(f'#sc_{index}').evaluate('(e)=>e.outerHTML')
                        frame=page.screenshot()
                        image=Image.open(io.BytesIO(frame)).convert('RGB')
                        if max(ImageStat.Stat(image).mean)<8:report['issues'].append({'scene':index,'reason':'Near-black sampled frame'})
                        name=f'review-frame-{index}.png';(target/name).write_bytes(frame)
                        report['frames'].append(name)
                        page.evaluate('(t)=>{window.__seek(t)}',scene['start']+.1)
                        page.evaluate('async(t)=>{window.__seek(t); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}',t)
                        repeated=Image.open(io.BytesIO(page.screenshot())).convert('RGB')
                        pixels=compare_pixels(image,repeated)
                        pixels['scene']=index
                        pixels['sameDOM']=before_dom==page.locator(f'#sc_{index}').evaluate('(e)=>e.outerHTML')
                        report['repeatSamples'].append(pixels)
                        if not pixels['withinTolerance'] or not pixels['sameDOM']:report['issues'].append({'scene':index,'reason':'Repeat seek changed geometry or exceeded raster tolerance'})
            report['issues'].extend({'reason':error} for error in errors)
        finally:browser.close()
    # One review sheet uses actual captured frames, never a generated mock-up.
    if report['frames']:
        from PIL import ImageDraw
        chosen=list(dict.fromkeys(round(i*(len(report['frames'])-1)/min(8,len(report['frames'])-1)) for i in range(min(9,len(report['frames']))))) if len(report['frames'])>1 else [0]
        sheet=Image.new('RGB',(1080,600*((len(chosen)+2)//3)),'#131d27')
        draw=ImageDraw.Draw(sheet)
        for slot,index in enumerate(chosen):
            image=Image.open(target/report['frames'][index]).convert('RGB');image.thumbnail((344,550))
            x=(slot%3)*360+(360-image.width)//2;y=(slot//3)*600
            sheet.paste(image,(x,y));draw.text(((slot%3)*360+12,y+563),f'Shot {index+1}',fill='#dce6ef')
        sheet.save(target/'contact-sheet.png')
        report['contactSheet']='contact-sheet.png'
    report['status']='needs_attention' if report['issues'] else 'sampled'
    return report


if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result=_inspect(Path(request['target']),request['plan'],request['aspect'])
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
