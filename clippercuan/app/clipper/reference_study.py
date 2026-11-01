"""Bounded local reference measurements; never infer factual or creative meaning."""
from __future__ import annotations

import math
import re
import statistics
import subprocess
from pathlib import Path

from .config import FFMPEG
from .media import _NO_WINDOW
from .shots import cuts_from_events, boundaries
from .editorial import hook_archetypes


def _timeline(words: list[dict], cuts: list[float], start: float, stop: float) -> list[dict]:
    """Evidence in equal temporal thirds, without inferring narrative roles."""
    words = sorted([w for w in words if float(w['e']) > start and float(w['s']) < stop], key=lambda w: float(w['s']))
    result = []
    for index, label in enumerate(('awal', 'tengah', 'akhir')):
        left = start + (stop-start)*index/3
        right = stop if index == 2 else start + (stop-start)*(index+1)/3
        selected = [word for word in words if left <= float(word['s']) < right]
        intervals = sorted((max(left, float(w['s'])), min(right, float(w['e'])))
                           for w in words if float(w['e']) > left and float(w['s']) < right)
        covered, previous = 0.0, left
        for a, b in intervals:
            covered += max(0, b-max(a, previous))
            previous = max(previous, b)
        local_cuts = [cut for cut in cuts if left-start <= cut < right-start]
        result.append({'part': label, 'start_relative_seconds': round(left-start, 3),
                       'end_relative_seconds': round(right-start, 3), 'cuts': len(local_cuts),
                       'words': len(selected), 'words_per_second': round(len(selected)/(right-left), 2) if words else None,
                       'transcript_coverage_percent': round(covered/(right-left)*100, 1) if words else None,
                       'excerpt': ' '.join(str(w['w']) for w in selected)[:240]})
    return result


def analyze(path: Path, words: list[dict], duration: float, start: float = 0, seconds: float = 60) -> dict:
    if not math.isfinite(duration) or not math.isfinite(start+seconds) or start < 0 or not 1 <= seconds <= 120 or start >= duration:
        raise ValueError('Pilih sampel 1–120 detik dalam video')
    stop=min(start+seconds,duration);span=stop-start
    command=[FFMPEG,'-hide_banner','-nostdin','-protocol_whitelist','file,pipe','-ss',str(start),'-t',str(span),'-i',str(path),
             '-vf',"scale=320:-2,select='gt(scene,0.015)',metadata=print:file=-",'-an','-f','null','-']
    result=subprocess.run(command,capture_output=True,timeout=90,creationflags=_NO_WINDOW)
    if result.returncode:raise ValueError('Sampel video tidak dapat dianalisis')
    raw=result.stdout.decode('utf-8','replace')
    times=re.findall(r'pts_time:([0-9.]+)',raw);scores=re.findall(r'lavfi.scene_score=([0-9.]+)',raw)
    cuts=cuts_from_events([(float(t),float(s)) for t,s in zip(times,scores)])
    shots=boundaries(cuts,span)
    transcript=sorted([w for w in words if start<=float(w['s'])<stop],key=lambda word:float(word['s']))
    pauses=[]
    for a,b in zip(transcript,transcript[1:]):
        if float(b['s'])-float(a['e'])>=.5:pauses.append({'start':round(float(a['e'])-start,3),'end':round(float(b['s'])-start,3)})
    hook=' '.join(str(w['w']) for w in transcript if float(w['s'])<start+3)
    return {'method':'local_scene_and_transcript_measurements','sample':{'start':start,'end':stop},
            'cuts_relative_seconds':cuts,'shots':len(shots),'median_shot_seconds':round(statistics.median(b-a for a,b in shots),3),
            'cuts_per_minute':round(len(cuts)*60/span,2),'transcript_words':len(transcript),
            'words_per_second':round(len(transcript)/span,2) if transcript else None,
            'transcript_pauses':pauses,'opening_transcript':hook,'hook':hook_archetypes(hook),
            'timeline_thirds':_timeline(words,cuts,start,stop),
            'transcript_status':'available' if transcript else 'not_available_in_sample',
            'manual_review':['Semantic hook/payoff and narrative structure are unmeasured',
                             'Temporal thirds are equal time windows, not automatic story segmentation',
                             'Transcript gaps are not acoustic silence measurements',
                             'Scene thresholds need real-video calibration; no style is copied automatically']}
