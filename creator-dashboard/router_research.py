"""9Router search protocol, separate from ordinary chat completions."""
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

from evidence import safe_url
from security import open_authenticated


def configuration(scope=''):
    prefix=scope.upper()+'_LLM_' if scope else 'LLM_'
    base=(os.getenv(prefix+'BASE_URL') or os.getenv('LLM_BASE_URL') or os.getenv('OPENAI_BASE_URL') or 'http://localhost:20128/v1').rstrip('/')
    key=os.getenv(prefix+'API_KEY') or os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY') or '9router-local'
    return base,key


def request(scope, path, payload=None):
    base,key=configuration(scope)
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with open_authenticated(req,timeout=120) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Response too large')
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValueError('Invalid object')
        return result
    except (OSError,ValueError) as exc:
        raise RuntimeError('Web search 9Router gagal. Periksa alamat gateway, autentikasi, versi yang mendukung /v1/search, dan provider Search di 9Router.') from exc


def routes(scope=''):
    catalogue=request(scope,'/models/web')
    rows=catalogue.get('data',[])
    if not isinstance(rows,list):raise RuntimeError('Katalog web search 9Router tidak valid')
    return list(dict.fromkeys(row['id'] for row in rows if isinstance(row,dict) and row.get('kind')=='webSearch' and isinstance(row.get('id'),str)))


def research(topic, context, scope=''):
    ids=routes(scope)
    route=os.getenv('RESEARCH_SEARCH_MODEL','').strip()
    if route and route not in ids:raise RuntimeError('RESEARCH_SEARCH_MODEL tidak ditemukan dalam katalog webSearch 9Router')
    if not route:
        if len(ids)!=1:raise RuntimeError('Pilih provider Search di 9Router dan atur RESEARCH_SEARCH_MODEL sesuai id dari /v1/models/web; ditemukan '+str(len(ids))+' pilihan')
        route=ids[0]
    query=(str(topic)+'\n'+str(context)[:800]).strip()[:1500]
    result=request(scope,'/search',{'model':route,'query':query,'max_results':8})
    rows=result.get('results',[])
    if not isinstance(rows,list):raise RuntimeError('Hasil web search 9Router tidak valid')
    sources=[];seen=set()
    for row in rows[:50]:
        if not isinstance(row,dict):continue
        try:url=safe_url(str(row.get('url','')))
        except ValueError:continue
        if url in seen:continue
        seen.add(url)
        sources.append({'id':len(sources)+1,'title':str(row.get('title') or url)[:500],
            'url':url,'publisher':urlsplit(url).hostname,'quality':'web',
            'excerpt':str(row.get('snippet') or '')[:4000],
            'publicationDate':row.get('published_at'),'retrievalStatus':'search_result',
            'claimVerification':'unverified'})
    if not sources:raise RuntimeError('9Router tidak menghasilkan sumber pencarian HTTPS; jawaban tanpa hasil pencarian tidak diterima')
    return {'provider':'9Router web search','model':route,'topic':topic,'queries':[query],
        'summary':'\n\n'.join(f"[{s['id']}] {s['title']}\n{s['excerpt']}" for s in sources),
        'sources':sources,'sourceCount':len(sources),'researchedAt':datetime.now(timezone.utc).isoformat(),
        'verified':False,'verificationStatus':'search_results_found_claims_unverified'}


if __name__ == '__main__':
    import argparse
    from security import redact_tree
    parser=argparse.ArgumentParser(description='Periksa katalog Search 9Router; tidak menampilkan API key')
    parser.add_argument('--scope',choices=['article','video'],default='video')
    parser.add_argument('--query',help='Opsional: jalankan pencarian nyata dengan query ini')
    args=parser.parse_args()
    try:
        if args.query:
            result=research(args.query,'',args.scope)
            output={'ok':True,'provider':result['provider'],'model':result['model'],'sources':result['sources']}
        else:
            ids=routes(args.scope)
            output={'ok':bool(ids),'search_models':ids,'note':'Bila lebih dari satu, atur RESEARCH_SEARCH_MODEL ke id yang dipilih. Gunakan --query untuk menguji pencarian nyata.'}
        print(json.dumps(redact_tree(output),ensure_ascii=False,indent=2))
        raise SystemExit(0 if output['ok'] else 1)
    except (RuntimeError,ValueError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False))
        raise SystemExit(1)
