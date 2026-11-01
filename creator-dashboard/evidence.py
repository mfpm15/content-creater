"""Explicit source/claim review. Grounding URLs are never proof by themselves."""
import hashlib
import re
import uuid
from datetime import date
from urllib.parse import urlsplit, parse_qsl


def safe_url(url: str) -> str:
    if len(url)>4096 or any(ord(char)<33 for char in url):raise ValueError('URL sumber tidak valid')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Sumber harus URL HTTPS tanpa credential')
    if any(re.search(r'token|secret|signature|credential|authorization|(?:^|[_-])key$',key,re.I)
           for key,_ in parse_qsl(parsed.query,keep_blank_values=True)) or parsed.fragment:
        raise ValueError('URL sumber tidak boleh mengandung credential query')
    return url


def claims(article: dict) -> list:
    result=[]
    for index,block in enumerate(article.get('blocks',[])):
        texts=[]
        if block.get('type') in {'p','callout'}: texts=[str(block.get('text',''))]
        elif block.get('type') in {'bullets','numbered'}: texts=block.get('items',[])
        elif block.get('type')=='table': texts=[' | '.join(map(str,row)) for row in block.get('rows',[])]
        for text in texts:
            if not text.strip(): continue
            key=hashlib.sha256(text.encode()).hexdigest()[:24]
            result.append({'id':key,'block':index,'text':text,'citations':re.findall(r'\[(\d+)\]',text)})
    return result


def update(ledger: dict, action: dict) -> dict:
    ledger.setdefault('sources',[]);ledger.setdefault('links',{});ledger.setdefault('history',[])
    kind=action.get('action')
    if kind=='source':
        if len(ledger['sources'])>=500:raise ValueError('Maksimal 500 sumber per artikel')
        source={'id':uuid.uuid4().hex,'url':safe_url(str(action.get('url','')).strip()),
                'title':str(action.get('title',''))[:500],'excerpt':str(action.get('excerpt',''))[:20000],
                'published_at':str(action.get('published_at','')),'verified':False}
        if source['published_at']: date.fromisoformat(source['published_at'])
        ledger['sources'].append(source)
    elif kind=='verify':
        source=next((s for s in ledger['sources'] if s['id']==action.get('source_id')),None)
        if not source or len(str(action.get('note','')).strip())<10 or not source['excerpt'].strip():
            raise ValueError('Sumber, kutipan bukti, dan catatan pemeriksaan minimal 10 karakter wajib')
        source.update(verified=True,review_note=str(action['note'])[:2000],review_kind='user_attestation_not_automatic_fact_check')
    elif kind=='link':
        ids=action.get('source_ids')
        if not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids) or any(i not in {s['id'] for s in ledger['sources']} for i in ids): raise ValueError('Pilih sumber yang dikenal')
        ledger['links'][str(action.get('claim_id'))]=list(dict.fromkeys(ids))
    else: raise ValueError('Aksi bukti tidak dikenal')
    ledger['revision']=int(ledger.get('revision',0))+1
    ledger['history'].append({'action':kind,'revision':ledger['revision']})
    return ledger


def audit(article: dict, ledger: dict | None = None, max_age_days: int = 0) -> dict:
    ledger=ledger or {};sources={s['id']:s for s in ledger.get('sources',[])};report=[]
    for claim in claims(article):
        linked=[sources[i] for i in ledger.get('links',{}).get(claim['id'],[]) if i in sources]
        acceptable=[]
        for source in linked:
            fresh=True
            if max_age_days:
                try: age=(date.today()-date.fromisoformat(source.get('published_at',''))).days;fresh=0<=age<=max_age_days
                except ValueError: fresh=False
            if source.get('verified') and source.get('excerpt') and fresh: acceptable.append(source['id'])
        report.append({**claim,'source_ids':[s['id'] for s in linked], 'status':'user_supported' if acceptable else 'needs_review'})
    return {'revision':ledger.get('revision',0),'sources':list(sources.values()),'claims':report,
            'unreviewed':sum(c['status']=='needs_review' for c in report),
            'method':'paragraph_claim_review_not_automatic_truth_verification','max_age_days':max_age_days}
