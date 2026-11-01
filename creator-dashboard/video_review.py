"""Measured media review with explicit coverage and unmeasured outcomes."""
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


def review(path: Path, duration: float, plan: dict | None = None) -> dict:
    ffprobe, ffmpeg = shutil.which('ffprobe'), shutil.which('ffmpeg')
    if not ffprobe: return {'status':'unmeasured','issues':['ffprobe unavailable']}
    proc = subprocess.run([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(path)],
                          capture_output=True,check=False,timeout=60)
    if proc.returncode: return {'status':'failed','issues':['Artifact could not be probed']}
    data=json.loads(proc.stdout); streams=data.get('streams',[])
    actual=float(data.get('format',{}).get('duration',0)); issues=[]
    video=next((s for s in streams if s.get('codec_type')=='video'),None)
    audio=any(s.get('codec_type')=='audio' for s in streams)
    if not video: issues.append('Missing video')
    if not audio: issues.append('Missing audio')
    if abs(actual-duration)>.5: issues.append('Duration differs from approved plan')
    measured={'status':'unmeasured'}
    if audio and ffmpeg:
        proc=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-protocol_whitelist','file,pipe','-i',str(path),'-vn',
                             '-af','ebur128=peak=true,silencedetect=noise=-40dB:d=0.5','-f','null','-'],capture_output=True,timeout=180)
        log=proc.stderr.decode('utf-8','replace'); tail=log[log.rfind('Summary:'):]
        loud=re.search(r'I:\s*(-?\d+(?:\.\d+)?)\s*LUFS',tail)
        peak=re.search(r'Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS',tail)
        if not proc.returncode and loud and peak:
            measured={'status':'measured','integrated_lufs':float(loud[1]),'true_peak_dbfs':float(peak[1]),
                      'silence_starts':[float(v) for v in re.findall(r'silence_start:\s*([\d.]+)',log)]}
            if abs(measured['integrated_lufs']+14)>2: issues.append('Loudness outside working target -14 ±2 LUFS')
            if measured['true_peak_dbfs']>-.5: issues.append('True peak too close to clipping')
        else: issues.append('Audio loudness/peak unmeasured')
    pacing=[]
    if plan:
        for scene in plan.get('scenes',[]):
            seconds=float(scene['end'])-float(scene['start'])
            rate=len(str(scene.get('narration','')).split())/seconds if seconds>0 else math.inf
            pacing.append({'scene':scene['id'],'words_per_second_estimate':round(rate,2),'needs_review':rate>4.5})
        if any(s['needs_review'] for s in pacing): issues.append('Narration pacing needs review')
    visual={'status':'unmeasured','reason':'No plan/HTML or video geometry'}
    beat_review={'status':'unmeasured','reason':'No known music markers'}
    manifest=path.parent/'audio-manifest.json'
    if plan and manifest.is_file():
        music=json.loads(manifest.read_text('utf-8')).get('music',{})
        markers=music.get('beat_markers',[])
        if markers:
            beat_review={'status':'measured_against_procedural_grid','method':music.get('beat_method'),
                         'cuts':[{'scene':s['id'],'at':s['start'],'nearest_peak_delta_seconds':round(min(abs(float(s['start'])-b) for b in markers),3)} for s in plan['scenes'][1:]],
                         'manual_required':'A cut need not land on a beat; approved timings remain unchanged'}
    if plan and video and (path.parent/'index.html').is_file():
        from visual_review import inspect
        visual=inspect(path.parent/'index.html',plan,int(video['width']),int(video['height']))
        if visual['status']=='needs_attention': issues.append('Text overflow found in sampled scenes')
    return {'status':'needs_attention' if issues else 'passed_media_checks','issues':issues,'duration':actual,
            'audio':measured,'pacing':pacing,'beat_review':beat_review,'visual_review':visual,'manual_required':True}
