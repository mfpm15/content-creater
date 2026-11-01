"""Explicit article review/revision tools. Source documents and prior revisions survive edits."""
import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from collections import Counter
from pathlib import Path

import article_drafter as ad
import article_storage
import evidence

LOCK=threading.RLock()
PROTECTED=re.compile(r'\[\d+(?:[,;\s]+\d+)*\]|(?:Rp\s*|\$)?\d+(?:[.,]\d+)*(?:\s*%)?|\b[A-Z]{2,}\b|\b(?:tidak|bukan|belum|jangan|not|never)\b|[“"]([^”"\n]+)[”"]')


def digest(article):
    return hashlib.sha256(json.dumps(article,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _private_write(path: Path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as output:json.dump(data,output,ensure_ascii=False,allow_nan=False)
        Path(name).replace(path)
    finally:Path(name).unlink(missing_ok=True)


def _article(slug):
    directory=ad._dir(slug);article=ad._read_json(directory/'article.json')
    if article is None:raise ValueError('Artikel belum selesai')
    return directory,article


def _idle(slug):
    if any(j['slug']==slug and j['status']=='running' for j in ad.JOBS.values()):raise ValueError('Tunggu proses artikel selesai')


def sections(article):
    starts=[i for i,b in enumerate(article['blocks']) if b['type']=='h2']
    return [{'index':n,'heading':article['blocks'][a]['text'],'start':a+1,'end':starts[n+1] if n+1<len(starts) else len(article['blocks'])} for n,a in enumerate(starts)]


def proposals(slug):
    directory,article=_article(slug)
    current=digest(article)
    rows=[]
    for path in sorted((directory/'revisions').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
        if not re.fullmatch(r'[a-f0-9]{32}',path.stem):continue
        item=ad._read_json(path,{})
        if item.get('status')=='proposed':rows.append({**item,'stale':item.get('base_revision')!=current})
    return rows


def evidence_report(slug):
    directory,article=_article(slug)
    ledger=ad._read_json(directory/'evidence.json',{})
    inp=ad._read_json(directory/'input.json',{})
    return evidence.audit(article,ledger,int(inp.get('freshness_days') or 0))


def update_evidence(slug,payload):
    with LOCK,ad._jobs_lock:
        _idle(slug);directory,article=_article(slug)
        ledger=ad._read_json(directory/'evidence.json',{})
        if type(payload.get('revision')) is not int or payload['revision']!=ledger.get('revision',0):raise ValueError('Laporan bukti berubah; muat ulang')
        if payload.get('action')=='link' and payload.get('claim_id') not in {c['id'] for c in evidence.claims(article)}:raise ValueError('Klaim sudah berubah/tidak dikenal')
        evidence.update(ledger,payload);_private_write(directory/'evidence.json',ledger)
        return evidence_report(slug)


def _fields(blocks):
    targets=[]
    for index,block in enumerate(blocks):
        if block['type'] in {'p','callout'}:targets.append((index,'text',None,block['text']))
        elif block['type'] in {'bullets','numbered'}:
            targets.extend((index,'items',j,text) for j,text in enumerate(block['items']))
    return targets


def propose_rewrite(slug,payload):
    with LOCK,ad._jobs_lock:
        _idle(slug);directory,article=_article(slug)
        if payload.get('article_revision')!=digest(article):raise ValueError('Artikel berubah; muat ulang')
        index=payload.get('section')
        if type(index) is not int or not 0<=index<len(sections(article)):raise ValueError('Pilih bagian yang valid')
        section=sections(article)[index];blocks=copy.deepcopy(article['blocks'][section['start']:section['end']]);targets=_fields(blocks)
    originals=[t[3] for t in targets]
    if not originals or sum(map(len,originals))>30000:raise ValueError('Bagian kosong/terlalu besar untuk revisi')
    def normalize(raw):
        texts=raw.get('texts') if isinstance(raw,dict) else None
        if not isinstance(texts,list) or len(texts)!=len(originals) or any(not isinstance(t,str) or not t.strip() for t in texts):raise ValueError('Jumlah/tipe paragraf revisi berubah')
        for old,new in zip(originals,texts):
            if Counter(m.group(0) for m in PROTECTED.finditer(old))!=Counter(m.group(0) for m in PROTECTED.finditer(new)):
                raise ValueError('Angka, sitasi, kutipan, akronim, atau negasi berubah; revisi ditolak')
        return {'texts':texts}
    result=ad._ask_json('Anda editor. Rapikan bahasa tanpa mengubah makna, urutan, angka, sitasi, kutipan, nama dan negasi. Balas JSON {"texts": [...]} dengan satu teks per input. Jangan menambahkan fakta.',
                        json.dumps({'instruction':str(payload.get('instruction','Rapikan klise dan ritme kalimat'))[:2000],'texts':originals},ensure_ascii=False),normalize)
    proposal={'id':uuid.uuid4().hex,'base_revision':digest(article),'section':index,'before':originals,'after':result['texts'],'status':'proposed'}
    _private_write(directory/'revisions'/(proposal['id']+'.json'),proposal)
    return proposal


def apply_rewrite(slug,payload):
    key=str(payload.get('proposal_id',''))
    if not re.fullmatch(r'[a-f0-9]{32}',key) or payload.get('approve') is not True:raise ValueError('Persetujuan proposal wajib')
    with LOCK,ad._jobs_lock,article_storage.LOCK:
        _idle(slug);directory,article=_article(slug)
        proposal=ad._read_json(directory/'revisions'/(key+'.json'))
        if not proposal or proposal['status']!='proposed' or proposal['base_revision']!=digest(article):raise ValueError('Proposal usang/tidak tersedia')
        section=sections(article)[proposal['section']]
        blocks=copy.deepcopy(article['blocks'][section['start']:section['end']])
        for target,text in zip(_fields(blocks),proposal['after']):
            i,field,j,_=target
            if j is None:blocks[i][field]=text
            else:blocks[i][field][j]=text
        backup=copy.deepcopy(article)
        article['blocks'][section['start']:section['end']]=blocks
        source=ad._read_json(directory/'sections'/f"{proposal['section']:02d}.json",{})
        source['blocks']=blocks
        proposal['status']='applied'
        updates={'article.json':article_storage.json_bytes(article),
                 f"sections/{proposal['section']:02d}.json":article_storage.json_bytes(source),
                 f'revisions/before-{key}.json':article_storage.json_bytes(backup),
                 f'revisions/{key}.json':article_storage.json_bytes(proposal)}
        article_storage.commit(directory,updates,article,ad._render_output_files)
        return ad.get_article(slug)


def add_diagram(slug,payload):
    from local_diagrams import render
    with LOCK,ad._jobs_lock,article_storage.LOCK:
        _idle(slug);directory,article=_article(slug)
        if payload.get('article_revision')!=digest(article):raise ValueError('Artikel berubah; muat ulang')
        key='diagram-'+uuid.uuid4().hex[:8]
        with tempfile.TemporaryDirectory(dir=directory,prefix='.diagram-') as folder:
            images=Path(folder)
            spec=render(payload.get('kind'),payload.get('labels'),images/(key+'.svg'),images/(key+'.png'))
            updates={f'images/{key}.{ext}':(images/(key+'.'+ext)).read_bytes() for ext in ('svg','png')}
        image={'id':key,'purpose':'Diagram lokal','aspect':'custom','alt':str(payload.get('title','Diagram'))[:300],
               'prompt':'Dibuat lokal dari label pengguna','style':'local-diagram','section':max(0,len(sections(article))-1),'diagram':spec}
        article['images'].append(image);article['blocks'].append({'type':'image','id':key,'caption':image['alt']})
        prompts=ad._read_json(directory/'prompts.json',[]);prompts.append(image)
        last=directory/'sections'/f"{image['section']:02d}.json"
        source=ad._read_json(last,{'blocks':[]});source['blocks'].append({'type':'image','id':key,'caption':image['alt']})
        updates.update({'article.json':article_storage.json_bytes(article),'prompts.json':article_storage.json_bytes(prompts),
                        str(last.relative_to(directory)):article_storage.json_bytes(source)})
        article_storage.commit(directory,updates,article,ad._render_output_files)
        return ad.get_article(slug)
