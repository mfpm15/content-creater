"""Local 24h/7d observations and explicit decisions; never automatic publishing."""
import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from video_job_store import _redact_tree

ROOT=Path(__file__).resolve().parent/'output'/'analytics'
LOCK=threading.RLock()
FIELDS={'views','likes','comments','shares','average_watch_seconds','completion_percent'}


def _path(key):
    if not re.fullmatch(r'[a-f0-9]{32}',key): raise ValueError('ID observasi tidak valid')
    target=(ROOT/(key+'.json')).resolve()
    if target.parent != ROOT.resolve(): raise ValueError('Lokasi observasi tidak valid')
    return target


def _save(data):
    ROOT.mkdir(parents=True,exist_ok=True)
    import tempfile, os
    fd,name=tempfile.mkstemp(dir=ROOT,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as output: json.dump(_redact_tree(data),output,ensure_ascii=False,allow_nan=False)
        Path(name).replace(_path(data['id']))
    finally: Path(name).unlink(missing_ok=True)


def create(payload: dict) -> dict:
    if not isinstance(payload,dict) or payload.get('window') not in {'24h','7d'} or payload.get('platform') not in {'youtube','reels','tiktok'}: raise ValueError('Platform/jendela observasi tidak valid')
    video=str(payload.get('video_id','')).strip()
    if not video or len(video)>128: raise ValueError('ID video wajib, maksimal 128 karakter')
    metrics=payload.get('metrics')
    if not isinstance(metrics,dict) or not metrics or set(metrics)-FIELDS: raise ValueError('Metrik observasi tidak valid')
    values={}
    for name,value in metrics.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0: raise ValueError('Metrik harus angka nonnegatif yang terbatas')
        if name=='completion_percent' and value>100: raise ValueError('Completion maksimal 100%')
        values[name]=value
    proposal='Bandingkan hook, durasi, dan payoff dengan hasil video lain; jangan simpulkan sebab-akibat dari satu observasi.'
    if values.get('completion_percent',100)<30: proposal='Usulkan eksperimen memperjelas hook/payoff; pertahankan faktor lain untuk perbandingan.'
    data={'id':uuid.uuid4().hex,'video_id':video,'platform':payload['platform'],'window':payload['window'],'metrics':values,
          'proposal':proposal,'status':'proposed','revision':1,'observed_at':datetime.now(timezone.utc).isoformat(),'history':[]}
    with LOCK: _save(data)
    return data


def list_observations() -> list:
    with LOCK:
        rows=[]
        for path in ROOT.glob('*.json'):
            try: rows.append(json.loads(_path(path.stem).read_text('utf-8')))
            except (OSError,ValueError): continue
        return sorted(rows,key=lambda row:row['observed_at'],reverse=True)[:100]


def decide(key: str, revision: int, approve: bool) -> dict:
    if type(revision) is not int or type(approve) is not bool: raise ValueError('Revisi dan keputusan wajib')
    with LOCK:
        data=json.loads(_path(key).read_text('utf-8'))
        if revision!=data['revision']: raise ValueError('Observasi berubah; muat ulang')
        data['history'].append({'status':data['status'],'at':datetime.now(timezone.utc).isoformat()})
        data.update(status='approved_experiment' if approve else 'rejected', revision=revision+1)
        _save(data)
        return data
