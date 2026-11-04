"""Original continuous-diagram adapter: absolute-time SVG, local render, measured review.

OneTake was studied for workflow ideas only; no upstream code, fonts or assets are used.
"""
import frame_rate
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from creative_profile import brand
from runtime_config import find_browser
from security import render_environment

CONCEPTS = [
    {'id': 'trace', 'name': 'Jejak ide', 'idea': 'Satu penanda menelusuri jalur yang membangun hubungan antaride.',
     'carry': 'Penanda yang sama berpindah sepanjang jalur.', 'look': 'Latar biru gelap, aksen hijau; ruang lega.',
     'excludes': 'Tanpa perpindahan kartu penuh.', 'accent': '#5ee5ac', 'background': '#102439', 'text': '#f5f7fa'},
    {'id': 'focus', 'name': 'Lensa penjelas', 'idea': 'Satu bingkai berubah ukuran untuk mengungkap detail secara berurutan.',
     'carry': 'Bingkai yang sama menjadi ruang untuk detail berikutnya.', 'look': 'Latar terang, tinta biru, aksen merah bata.',
     'excludes': 'Tanpa kamera acak atau partikel.', 'accent': '#bd5139', 'background': '#faf7ef', 'text': '#24334b'},
    {'id': 'assemble', 'name': 'Bangun hasil', 'idea': 'Komponen bertambah di dalam satu wadah sampai menjadi satu hasil.',
     'carry': 'Wadah dan komponen sebelumnya tetap terlihat.', 'look': 'Latar arang, aksen kuning lembut.',
     'excludes': 'Maksimal 12 beat/komponen; hasil sebelumnya tetap terlihat.', 'accent': '#e8c36a', 'background': '#24252b', 'text': '#fff8ed'},
]


def design(raw: dict, scenes: list[dict], duration: float) -> dict:
    if not isinstance(raw, dict) or raw.get('concept') not in {c['id'] for c in CONCEPTS}:
        raise ValueError('Pilih satu dari tiga konsep gerak kontinu')
    rest = raw.get('restFraction', .35)
    voice = raw.get('voiceMode', 'music')
    if type(rest) not in (int, float) or not .15 <= rest <= .7:
        raise ValueError('Porsi jeda gerak harus 0.15–0.7')
    if voice not in {'music', 'tts'}:
        raise ValueError('Audio kontinu harus music atau tts')
    if raw['concept']=='assemble' and len(scenes)>12:
        raise ValueError('Konsep Bangun hasil maksimal 12 beat; ringkas rencana atau pilih konsep lain')
    previous = 0.0
    for scene in scenes:
        if abs(scene['start']-previous) > .005:
            raise ValueError('Film kontinu membutuhkan adegan berurutan tanpa celah, mulai detik 0')
        previous = scene['end']
    if abs(previous-duration) > .005:
        raise ValueError('Adegan film kontinu harus mencakup seluruh durasi rencana')
    return {'concept': raw['concept'], 'restFraction': float(rest), 'voiceMode': voice,
            'fps': frame_rate.validate(raw.get('fps',30)), 'quality': 'draft', 'carrier': 'motion-hero'}


def beat_sheet(plan: dict) -> dict:
    cfg = design({**plan['motionDesign'],'fps':frame_rate.get(plan)}, plan['scenes'], plan['duration'])
    transitions = []
    scenes = plan['scenes']
    for a, b in zip(scenes, scenes[1:]):
        half = min(.6, min(a['duration'], b['duration'])*(1-cfg['restFraction'])/2)
        transitions.append({'at': b['start'], 'start': b['start']-half, 'end': b['start']+half})
    beats = []
    for i, scene in enumerate(scenes):
        left = transitions[i-1]['end'] if i else scene['start']
        right = transitions[i]['start'] if i < len(transitions) else scene['end']
        beats.append({'scene': scene['id'], 'start': scene['start'], 'end': scene['end'],
                      'holdStart': left, 'holdEnd': right, 'carrier': cfg['carrier'],
                      'picture': scene['visual'], 'soundCue': scene.get('soundCue', '')})
    durations = [s['duration'] for s in scenes]
    average = sum(durations)/len(durations)
    variation = (sum((d-average)**2 for d in durations)/len(durations))**.5/average
    return {'beats': beats, 'transitions': transitions, 'duration_variation': round(variation, 3),
            'advisories': ['Durasi adegan seragam; periksa ritme tanpa mengubah timecode secara otomatis.'] if len(scenes)>1 and variation<.15 else [],
            'scope': 'Authored timing, not a measurement of rendered pixels or narrative quality'}


def composition(plan: dict, aspect: dict) -> str:
    cfg = design({**plan['motionDesign'],'fps':frame_rate.get(plan)}, plan['scenes'], plan['duration'])
    concept = next(row for row in CONCEPTS if row['id'] == cfg['concept'])
    palette = brand(plan.get('brand') or {'name': concept['name'], **{k: concept[k] for k in ('accent', 'background', 'text')}})
    sheet = beat_sheet(plan)
    data = {'duration': plan['duration'], 'width': aspect['width'], 'height': aspect['height'],
            'design': cfg, 'palette': palette, 'sheet': sheet,
            'scenes': [{key: scene.get(key, '') for key in ('id', 'start', 'end', 'narration', 'onScreenText', 'soundCue', 'visualFamily')}
                       for scene in plan['scenes']]}
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return TEMPLATE.replace('__DATA_JSON__', serialized)


TEMPLATE = '''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src data:">
<title>Continuous Motion Preview</title><style>
*{box-sizing:border-box}body{margin:0;overflow:hidden}#stage{position:relative;width:100vw;height:100vh;overflow:hidden}
svg{width:100%;height:100%;position:absolute;inset:0}.hero-title{position:absolute;top:13%;left:12%;width:76%;margin:0;text-align:center;line-height:1.1;overflow-wrap:anywhere;font-weight:800}
.subtitle{position:absolute;bottom:17%;left:14%;width:72%;text-align:center;line-height:1.4;overflow-wrap:anywhere;max-height:22%;overflow:hidden}
.wordmark{position:absolute;top:5%;left:15%;width:70%;text-align:center;white-space:pre-wrap}
.controls{position:absolute;bottom:10px;left:8%;width:84%;display:flex;gap:10px;align-items:center}.controls input{flex:1;min-width:0}
html[data-capture] .controls{display:none}
</style></head><body><main id="stage"><svg id="world" xmlns="http://www.w3.org/2000/svg" aria-label="Diagram gerak kontinu">
<path id="route" fill="none" stroke-width="4" opacity=".35"/><g id="details"></g><rect id="motion-hero" stroke-width="5"/><g id="tiles"></g>
</svg><div class="wordmark" id="mark"></div><h1 class="hero-title" id="headline"></h1><p class="subtitle" id="caption"></p>
<div class="controls"><button id="play" type="button">Putar</button><input id="seek" type="range" min="0" step="0.01" aria-label="Waktu preview"><span id="time"></span></div></main>
<script id="motion-data" type="application/json">__DATA_JSON__</script><script>
'use strict';
const D=JSON.parse(document.getElementById('motion-data').textContent),NS='http://www.w3.org/2000/svg';
const byId=id=>document.getElementById(id),stage=byId('stage'),hero=byId('motion-hero'),route=byId('route'),world=byId('world');
const W=D.width,H=D.height,scenes=D.scenes,concept=D.design.concept,p=D.palette;
world.setAttribute('viewBox',`0 0 ${W} ${H}`);stage.style.background=p.background;stage.style.color=p.text;stage.style.fontFamily=p.font;
route.setAttribute('stroke',p.accent);hero.setAttribute('stroke',p.accent);hero.setAttribute('fill',concept==='trace'?p.accent:p.background);
byId('mark').textContent=p.wordmark;byId('seek').max=D.duration;
function node(tag,attrs,parent){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n}
const tiles=Array.from({length:Math.min(12,scenes.length)},()=>node('rect',{fill:p.accent,rx:8},byId('tiles')));
const details=Array.from({length:5},(_,i)=>node('rect',{x:W*(.2+i*.12),y:H*(.46+(i%2)*.03),width:W*.08,height:H*.07,rx:12,fill:p.accent,opacity:.12},byId('details')));
const clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,u)=>a+(b-a)*u;
function shape(i){
 if(concept==='trace'){const locations=[[.24,.48],[.7,.54],[.4,.61],[.73,.43],[.32,.56]],v=locations[i%locations.length];return [v[0]*W,v[1]*H,W*.04,W*.04,W*.02]}
 if(concept==='focus'){const sizes=[[.44,.22],[.24,.12],[.58,.28],[.3,.16]],v=sizes[i%sizes.length];return [W*(.5+(i%2? .08:-.06)),H*.51,W*v[0],H*v[1],18]}
 const n=Math.min(12,i+1);return [W*.5,H*.52,W*(.34+Math.min(n,6)*.035),H*(.17+Math.ceil(n/4)*.045),22];
}
let current=0,playing=false,clock=0,lastVisualKey='';
function draw(seconds){
 const t=Math.max(0,Math.min(D.duration,Number.isFinite(seconds)?seconds:0));current=t;
 let i=Math.max(0,scenes.findIndex(s=>t>=s.start&&t<s.end));if(t===D.duration)i=scenes.length-1;
 let from=i,to=i,u=0;
 for(let k=0;k<D.sheet.transitions.length;k++){const edge=D.sheet.transitions[k];if(t>=edge.start&&t<=edge.end){from=k;to=k+1;const x=clamp((t-edge.start)/(edge.end-edge.start));u=(1-Math.cos(Math.PI*x))/2;break}}
 const key=`${innerWidth}x${innerHeight}:${i}:${from}:${to}:${u}`;
 window.__renderKey=key;
 byId('seek').value=t;byId('time').textContent=t.toFixed(1)+'s';
 if(key===lastVisualKey)return true;
 lastVisualKey=key;
 const a=shape(from),b=shape(to),s=a.map((v,j)=>mix(v,b[j],u));
 hero.setAttribute('x',s[0]-s[2]/2);hero.setAttribute('y',s[1]-s[3]/2);hero.setAttribute('width',s[2]);hero.setAttribute('height',s[3]);hero.setAttribute('rx',s[4]);
 route.setAttribute('d',concept==='trace'?'M '+Array.from({length:from+1},(_,n)=>shape(n).slice(0,2).join(' ')).concat([s.slice(0,2).join(' ')]).join(' L '):'');
 byId('details').setAttribute('opacity',concept==='focus'?1:0);
 tiles.forEach((tile,j)=>{const on=concept==='assemble'&&j<=to;tile.setAttribute('opacity',on?(j===to&&to!==from?u:.85):0);tile.setAttribute('x',s[0]-s[2]*.37+(j%4)*s[2]*.2);tile.setAttribute('y',s[1]-s[3]*.3+Math.floor(j/4)*s[3]*.23);tile.setAttribute('width',s[2]*.14);tile.setAttribute('height',s[3]*.16)});
 // Text changes belong to the persistent world; no independent scene containers are swapped.
 const title=scenes[i].onScreenText||'',caption=scenes[i].narration||'';
 byId('headline').textContent=title;byId('caption').textContent=caption;
 const scale=Math.min(innerWidth/W,innerHeight/H);
 byId('headline').style.fontSize=Math.max(8,Math.min(W*.065,H*.065)*scale)+'px';
 byId('caption').style.fontSize=Math.max(8,Math.min(W*.032,H*.035)*scale)+'px';
 for(const [id,budget] of [['headline',.18],['caption',.18]]) {
   const el=byId(id);let fs=parseFloat(el.style.fontSize);
   while((el.scrollHeight>innerHeight*budget || el.scrollWidth>el.clientWidth+1) && fs>14*scale){fs-=scale;el.style.fontSize=fs+'px';}
 }
 byId('mark').style.fontSize=Math.max(8,Math.min(W*.024,H*.025)*scale)+'px';
 byId('seek').value=t;byId('time').textContent=t.toFixed(1)+'s';return true;
}
window.__seek=t=>{playing=false;byId('play').textContent='Putar';return draw(t)};
window.__timelines={video:{seek:window.__seek,pause(){playing=false},duration(){return D.duration}}};
window.__meta={duration:D.duration,fps:D.design.fps,concept,carrier:'motion-hero',motionBlur:false};
window.__track=()=>{const b=hero.getBoundingClientRect();return {id:'motion-hero',x:b.x,y:b.y,width:b.width,height:b.height,opacity:1,viewportWidth:innerWidth,viewportHeight:innerHeight}};
window.__events=()=>scenes.filter(s=>s.soundCue).map(s=>({time:s.start,cue:s.soundCue}));
window.__ready=document.fonts.ready.then(()=>draw(0));
byId('seek').oninput=event=>window.__seek(Number(event.target.value));
byId('play').onclick=()=>{playing=!playing;clock=performance.now();byId('play').textContent=playing?'Jeda':'Putar'};
function tick(now){if(playing){draw((current+(now-clock)/1000)%D.duration)}clock=now;requestAnimationFrame(tick)}requestAnimationFrame(tick);
window.addEventListener('resize',()=>draw(current));
</script></body></html>'''


def runtime_issues() -> list[str]:
    missing = []
    for name in ('ffmpeg', 'ffprobe'):
        if not shutil.which(name): missing.append(name)
    if importlib.util.find_spec('playwright') is None: missing.append('Playwright dashboard')
    if not find_browser(): missing.append('Chrome/Edge/Chromium')
    return missing


@contextmanager
def _serve(source: Path):
    """Serve exactly one trusted composition, never the output directory."""
    content=source.read_bytes()
    if len(content)>4_000_000:raise ValueError('Composition exceeds 4 MB')
    route='/'+uuid.uuid4().hex+'.html'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!=route or self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(content)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}'+route
    finally:server.shutdown();thread.join(5);server.server_close()


def _probe(page, plan: dict, width: int, height: int) -> dict:
    boundaries = []
    sheet = beat_sheet(plan)
    for edge in sheet['transitions']:
        points = [edge['start']+(edge['end']-edge['start'])*.25, edge['start']+(edge['end']-edge['start'])*.75]
        boxes = []
        for t in points:
            page.evaluate('(t)=>{window.__seek(t)}', t)
            boxes.append(page.evaluate('window.__track()'))
        a, b = boxes
        distance = math.hypot((a['x']+a['width']/2)-(b['x']+b['width']/2), (a['y']+a['height']/2)-(b['y']+b['height']/2))
        size_delta = max(abs(a['width']-b['width']), abs(a['height']-b['height']))
        visible = all(v['opacity']>0 and v['width']>0 and v['height']>0 for v in boxes)
        boundaries.append({'at':edge['at'], 'carrier':a['id'], 'status':'carried' if visible and a['id']==b['id'] and max(distance,size_delta)>1 else 'anchored' if visible else 'bare',
                           'center_travel_px':round(distance,3),'size_delta_px':round(size_delta,3),'samples':boxes})
    errors = []
    for beat in sheet['beats']:
        t = (beat['start']+beat['end'])/2
        page.evaluate('(t)=>{window.__seek(t)}',t)
        box = page.evaluate('window.__track()')
        if box['x']<0 or box['y']<0 or box['x']+box['width']>width+1 or box['y']+box['height']>height+1:
            errors.append({'scene':beat['scene'],'code':'carrier_out_of_frame'})
        overflow = page.evaluate("""()=>[...document.querySelectorAll('.hero-title,.subtitle,.wordmark')].some(e=>{const b=e.getBoundingClientRect();return e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2||b.left<0||b.right>innerWidth+1||b.top<0||b.bottom>innerHeight+1})""")
        if overflow: errors.append({'scene':beat['scene'],'code':'text_overflow'})
    middle = plan['duration']*.5
    page.evaluate('(t)=>{window.__seek(t)}',middle)
    first = page.locator('#stage').screenshot(animations='disabled')
    page.evaluate('(t)=>{window.__seek(t)}',plan['duration']*.1)
    page.evaluate('(t)=>{window.__seek(t)}',middle)
    repeat = page.locator('#stage').screenshot(animations='disabled')
    deterministic = hashlib.sha256(first).digest()==hashlib.sha256(repeat).digest()
    if not deterministic: errors.append({'code':'non_deterministic_seek'})
    return {'status':'needs_attention' if errors else 'sampled', 'method':'authored_boundary_dom_tracking_and_repeat_pixels',
            'boundaries':boundaries,'boundary_count_expected':len(plan['scenes'])-1,'deterministic_repeat':deterministic,
            'repeat_sample_seconds':middle,'continuity_status':'measured_primary_carrier' if boundaries else 'not_measured_no_boundary',
            'issues':errors,'motion_blur':False,'manual_required':True,
            'limitations':['Primary carrier only, not semantic understanding or all visual elements',
                           'Layout sampled at scene midpoints; no claim of all-frame safe area',
                           'Single-frame capture; no shutter motion blur or 4K60 claim']}


def pixel_motion(video: Path) -> dict:
    """Low-resolution luminance differences from the encoded video, not the plan."""
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:return {'status':'unmeasured','reason':'FFmpeg unavailable'}
    try:
        result=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-i',str(video),
            '-vf','fps=10,scale=160:-2,tblend=all_mode=difference,signalstats,metadata=print:file=-',
            '-an','-f','null','-'],capture_output=True,timeout=60,env=render_environment())
        values=[float(value) for value in re.findall(rb'lavfi.signalstats.YAVG=([0-9.]+)',result.stdout)]
        if result.returncode or not values:raise ValueError('No pixel samples')
        return {'status':'measured','method':'encoded_luminance_absolute_difference','sample_fps':10,'analysis_width':160,
                'samples':len(values),'low_change_threshold_8bit':.1,
                'low_change_fraction':round(sum(value<=.1 for value in values)/len(values),4),
                'max_mean_change_8bit':round(max(values),4),
                'limitations':'Low-resolution area average can miss small objects; text changes also contribute. Not aesthetic validation.'}
    except (OSError,ValueError,subprocess.SubprocessError):
        return {'status':'unmeasured','reason':'Pixel analyzer unavailable or timed out'}


def render(directory: Path, plan: dict, aspect: dict, progress=None, timeout: float = 600,
           reuse_static_frames: bool = True) -> tuple[Path, dict]:
    """Stream one PNG frame at a time to FFmpeg. One browser, no render queue."""
    missing = runtime_issues()
    if missing: raise RuntimeError('Runtime kontinu belum siap: '+', '.join(missing))
    from playwright.sync_api import sync_playwright
    source = directory/'index.html'
    if source.is_symlink() or not source.is_file(): raise ValueError('Composition must be a regular local file')
    width,height = aspect['width'],aspect['height']
    if type(width) is not int or type(height) is not int or not (16<=width<=3840 and 16<=height<=3840) or width%2 or height%2:
        raise ValueError('Render dimensions must be even and bounded')
    if not 0<float(plan['duration'])<=600: raise ValueError('Render duration out of bounds')
    fps=frame_rate.get(plan)
    frames = math.ceil(plan['duration']*fps)
    target = directory/'silent.mp4'
    temporary = directory/'silent.part.mp4'
    env = render_environment()
    command = [shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-nostdin','-y','-f','image2pipe','-vcodec','png','-r',str(fps),
               '-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','fast','-pix_fmt','yuv420p','-frames:v',str(frames),
               '-map_metadata','-1','-movflags','+faststart',str(temporary)]
    started = time.monotonic()
    try:
        with tempfile.TemporaryFile() as errors, _serve(source) as uri, sync_playwright() as manager:
            browser = manager.chromium.launch(executable_path=find_browser(), env=env,
                      chromium_sandbox=os.getenv('VIDEO_REVIEW_ALLOW_NO_SANDBOX')!='1')
            try:
                page = browser.new_page(viewport={'width':width,'height':height},service_workers='block',accept_downloads=False)
                page.route('**/*',lambda route:route.continue_() if route.request.url==uri else route.abort())
                page_errors=[]
                page.on('pageerror',lambda error:page_errors.append(str(error)[:120]))
                page.goto(uri,wait_until='load',timeout=20000)
                page.evaluate('async()=>{await window.__ready;document.documentElement.dataset.capture="1";window.__seek(0)}')
                report = _probe(page,plan,width,height)
                if not report['deterministic_repeat']:raise RuntimeError('Seek changed pixels on repeat')
                process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors,env=env)
                timer = threading.Timer(max(.1,timeout-(time.monotonic()-started)),process.kill)
                timer.daemon=True;timer.start()
                captured=0;last_key=None;last_png=None
                try:
                    for frame in range(frames):
                        if time.monotonic()-started>timeout:raise TimeoutError('Continuous render timed out')
                        key=page.evaluate('(t)=>{window.__seek(t);return window.__renderKey}',frame/fps)
                        if not reuse_static_frames or not isinstance(key,str) or not key or last_png is None or key!=last_key:
                            last_png=page.locator('#stage').screenshot(timeout=15000,animations='disabled')
                            captured+=1
                        last_key=key
                        process.stdin.write(last_png)
                        if progress and frame%fps==0:progress(frame/frames)
                    process.stdin.close()
                    if process.wait(timeout=30):raise RuntimeError('FFmpeg encode failed')
                finally:
                    timer.cancel()
                    if process.poll() is None:process.kill()
                    process.wait(timeout=10)
                    if process.stdin and not process.stdin.closed:process.stdin.close()
                if page_errors:raise RuntimeError('Composition raised a browser error')
                temporary.replace(target)
                report.update(frames=frames,fps=fps,captured_frames=captured,reused_static_frames=frames-captured,
                              capture_optimization='consecutive_identical_authored_visual_state' if reuse_static_frames else 'disabled',
                              wall_seconds=round(time.monotonic()-started,3),
                              composition_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                return target,report
            finally:browser.close()
    finally:temporary.unlink(missing_ok=True)
