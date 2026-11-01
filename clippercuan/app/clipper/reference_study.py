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


def analyze(path: Path, words: list[dict], duration: float, start: float = 0, seconds: float = 60) -> dict:
    if not math.isfinite(start+seconds) or start < 0 or not 1 <= seconds <= 120 or start >= duration:
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
    transcript=[w for w in words if start<=float(w['s'])<stop]
    pauses=[]
    for a,b in zip(transcript,transcript[1:]):
        if float(b['s'])-float(a['e'])>=.5:pauses.append({'start':round(float(a['e'])-start,3),'end':round(float(b['s'])-start,3)})
    hook=' '.join(str(w['w']) for w in transcript if float(w['s'])<start+3)
    return {'method':'local_scene_and_transcript_measurements','sample':{'start':start,'end':stop},
            'cuts_relative_seconds':cuts,'shots':len(shots),'median_shot_seconds':round(statistics.median(b-a for a,b in shots),3),
            'cuts_per_minute':round(len(cuts)*60/span,2),'transcript_words':len(transcript),
            'words_per_second':round(len(transcript)/span,2) if transcript else None,
            'transcript_pauses':pauses,'opening_transcript':hook,'hook':hook_archetypes(hook),
            'manual_review':['Semantic hook/payoff and narrative structure are unmeasured',
                             'Transcript gaps are not acoustic silence measurements',
                             'Scene thresholds need real-video calibration; no style is copied automatically']}
