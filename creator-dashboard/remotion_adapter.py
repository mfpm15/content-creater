"""Video Studio → original, asset-free Remotion composition. No daemon dependency."""
from __future__ import annotations

import frame_rate
import renderer_contract
import scene_diagram
import html
import json
import math
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import creative_profile
import scene_render
import video_templates
import caption_design
import media_library
from runtime_config import find_browser
from security import redact, render_environment

APP = Path(__file__).parent/'apps'/'video-studio-remotion'
FPS = 30


def runtime_issues() -> list[str]:
    missing=[]
    if not shutil.which('node'):missing.append('Node.js 22+')
    if not (APP/'node_modules'/'@remotion'/'renderer'/'package.json').is_file():missing.append('Remotion runtime: jalankan setup-core.bat')
    if not find_browser():missing.append('Chrome/Edge')
    if not shutil.which('ffmpeg'):missing.append('FFmpeg')
    return missing


def _frame(seconds: float, fps: int = FPS) -> int:
    return math.floor(float(seconds)*fps+.5)


def manifest(plan: dict, aspect: dict) -> tuple[dict,dict]:
    """Keep approved timings. Reject gaps rather than silently retiming a film."""
    fps=frame_rate.get(plan)
    frame=lambda seconds:_frame(seconds,fps)
    total=frame(plan['duration'])
    if not 1<=total<=600*fps:raise ValueError('Durasi Remotion harus 1 frame–600 detik')
    width,height=aspect['width'],aspect['height']
    if any(type(n) is not int or not 128<=n<=3840 or n%2 for n in (width,height)):raise ValueError('Kanvas Remotion tidak valid')
    shots,captions,methods=[],[],[]
    cursor=0
    for scene in plan['scenes']:
        start,end=frame(scene['start']),frame(scene['end'])
        if start!=cursor or end<=start or end>total:raise ValueError('Adegan Remotion wajib menutup durasi tanpa gap/overlap, minimal satu frame per adegan')
        controls=scene_render.validate(scene.get('renderControls',{}))
        family=scene.get('visualFamily')
        family=family if family in {'process','data','comparison'} else 'concept'
        # Never turn an invented decorative bar into a factual data chart.
        # Keep approved signs/decimals; prefer the headline to duplicate narration.
        numbers=renderer_contract.literal_numbers(scene)
        subject=' '.join(n for n in numbers[:3] if len(n)<=30) if family=='data' else str(scene.get('subject',''))[:200]
        shots.append({'id':scene['id'],'startFrame':start,'endFrame':end,'title':scene['onScreenText'],
                      'subject':subject,'family':family,**controls})
        if 'diagram' in scene:shots[-1]['diagram']=scene_diagram.validate(scene['diagram'])
        if scene.get('assetId'):
            meta,_ = media_library.get(scene['assetId'])
            shots[-1]['assetFile'] = 'media/'+meta['filename']
        cues=scene.get('wordCues')
        if cues:
            groups=[cues[i:i+7] for i in range(0,len(cues),7)]
            for group in groups:
                a=min(end-1,max(start,frame(group[0]['start'])))
                b=min(end,max(a+1,frame(group[-1]['end'])))
                if captions and a<captions[-1]['endFrame']:a=captions[-1]['endFrame']
                if b>a:
                    words=[]
                    for cue in group:
                        x=max(a,min(b-1,frame(cue['start'])))
                        y=max(x+1,min(b,frame(cue['end'])))
                        words.append({'text':cue['word'],'startFrame':x,'endFrame':y})
                    captions.append({'startFrame':a,'endFrame':b,'text':' '.join(cue['word'] for cue in group),'wordFrames':words})
            methods.append({'scene':scene['id'],'method':'edge_tts_word_boundaries_rounded_to_frames' if scene.get('wordCueSource')=='edge_tts' else 'supplied_word_cues_rounded_to_frames'})
        else:
            # Full text is preserved. Estimated visual pacing is not forced alignment.
            words=scene['narration'].split()
            groups=[];current=[]
            for word in words:
                if current and (len(current)>=7 or len(' '.join(current+[word]))>75):groups.append(current);current=[]
                current.append(word)
            if current:groups.append(current)
            if len(groups)>end-start:raise ValueError('Narasi terlalu padat untuk jumlah frame adegan')
            for i,group in enumerate(groups):
                a=start+(end-start)*i//len(groups);b=start+(end-start)*(i+1)//len(groups)
                captions.append({'startFrame':a,'endFrame':b,'text':' '.join(group)})
            methods.append({'scene':scene['id'],'method':'estimated_text_chunks_not_audio_alignment'})
        cursor=end
    if not shots or cursor!=total:raise ValueError('Adegan Remotion harus mencakup seluruh durasi')
    if any(len(shot['title'])>500 for shot in shots) or any(len(c['text'])>500 for c in captions):raise ValueError('Teks Remotion terlalu panjang; ringkas judul atau token narasi')
    brand=creative_profile.brand(plan.get('brand') or creative_profile.DEFAULT)
    chosen=video_templates.get(plan["templateId"]) if plan.get("templateId") else None
    props={'version':1,'width':width,'height':height,'fps':fps,'totalFrames':total,'topic':plan['topic'], 'captionStyle':caption_design.validate(plan.get('captionStyle')), 'layout':chosen['layout'] if chosen else 'editorial', 'effect':chosen['effect'] if chosen else 'minimal',
           'brand':{key:brand[key] for key in ('background','accent','text','wordmark','font')},'shots':shots,'captions':captions}
    return props,{'adapter':'remotion','version':'4.0.540','caption_timing':methods,
                  'visual_families':['process','data','comparison','concept'],
                  'templateId':chosen['id'] if chosen else None, 'captionStyle':caption_design.validate(plan.get('captionStyle')),
                  'manual_required':'Story, semantics, readability and audio/caption timing require review'}


def preview(plan: dict) -> str:
    return '<!doctype html><html lang="id"><meta charset="utf-8"><title>'+html.escape(plan['topic'])+'</title><body style="background:#080f20;color:#fff;font:18px Arial;padding:24px"><h1>'+html.escape(plan['topic'])+'</h1><p>Frame hasil render Remotion. Caption tanpa cue kata memakai estimasi, bukan alignment audio.</p><div id="frames"></div><script>for(let i=0;i<6;i++){const image=new Image();image.src="review-frame-"+i+".png";image.style="max-width:30%;margin:1%";image.onerror=()=>image.remove();document.querySelector("#frames").append(image)}</script></body></html>'


def render(target: Path, plan: dict, aspect: dict) -> tuple[Path,dict]:
    missing=runtime_issues()
    if missing:raise RuntimeError('Runtime Remotion belum siap: '+', '.join(missing))
    props,report=manifest(plan,aspect)
    asset_ids=list(dict.fromkeys(shot['assetId'] for shot in plan['scenes'] if shot.get('assetId')))
    report['visual_assets']=[media_library.stage(asset_id,target/'public') for asset_id in asset_ids]
    output=target/'silent.mp4'
    with tempfile.TemporaryDirectory(prefix='.remotion-',dir=target) as folder:
        source=Path(folder)/'timeline.json'
        source.write_text(json.dumps(props,ensure_ascii=False,allow_nan=False),encoding='utf-8');source.chmod(0o600)
        command=['node',str(APP/'render.mjs'),str(source.resolve()),str(output.resolve()),str(find_browser())]
        kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
        process=subprocess.Popen(command,cwd=APP,env=render_environment(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
        try:
            stdout,stderr=process.communicate(timeout=600)
            if process.returncode:raise RuntimeError('Render Remotion gagal: '+redact(stderr.decode('utf-8','replace'))[-1500:])
            rows=[json.loads(line) for line in stdout.decode().splitlines() if line.startswith('{')]
            report['frames']=next((row['frames'] for row in rows if 'frames' in row),[])
            report['layout']=next((row['layout'] for row in rows if 'layout' in row),{'observed_frames':0,'issues':[]})
            report['deterministic_repeat']=any(row.get('deterministic_repeat') is True for row in rows)
            if not output.is_file() or not report['frames']:raise RuntimeError('Remotion tidak menghasilkan video/frame review')
        except BaseException:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                else:os.killpg(process.pid,signal.SIGKILL)
                process.communicate(timeout=15)
            output.unlink(missing_ok=True)
            raise
    (target/'remotion-timeline.json').write_text(json.dumps(props,ensure_ascii=False),encoding='utf-8')
    (target/'render-report.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    return output,report
