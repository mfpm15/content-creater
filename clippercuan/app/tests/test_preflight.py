import copy
import math
import queue

import pytest

from clipper import candidates, highlights, media, preflight, project


@pytest.mark.parametrize('start,end', [(math.nan,10),(0,math.inf),(-1,3),(4,4),(5,4),(0,61),(True,4)])
def test_invalid_times_cannot_render(start,end):
    check=preflight.analyze({'start':start,'end':end},60,[])
    assert not check['can_render'] and check['errors']


def test_review_warnings_never_remove_words_or_block_valid_clip():
    words=[{'w':'tidak','s':.8,'e':1.4},{'w':'25','s':2,'e':2.4}]
    original=copy.deepcopy(words)
    check=preflight.analyze({'start':1,'end':3},60,words)
    assert check['can_render'] and any('memotong kata' in warning for warning in check['warnings'])
    assert check['word_count']==2 and words==original
    empty=preflight.analyze({'start':0,'end':3},None,[])
    assert empty['can_render'] and len(empty['warnings'])==2


def test_clip_override_uses_relative_timestamps_and_explicit_empty_track():
    check=preflight.analyze({'start':20,'end':24,'words':[{'w':'tidak','s':0,'e':1}]},60,[])
    assert check['word_count']==1 and check['caption_track']=='clip_override'
    empty=preflight.analyze({'start':20,'end':24,'words':[]},60,[{'w':'lama','s':21,'e':22}])
    assert empty['word_count']==0


@pytest.mark.parametrize('value',[math.nan,math.inf,-math.inf,None,True,{},'invalid'])
def test_create_and_edit_reject_nonfinite_times_without_mutating(isolated_project,value):
    pid=isolated_project['id']
    project._JOBS.get_nowait()
    project.update(pid,media={'duration':30},candidates=[{'id':'clip_01','start':0,'end':10,'status':'draft_candidate'}])
    before=project.load(pid)
    with pytest.raises(ValueError,match='terbatas'):project.add_clip(pid,value,10)
    with pytest.raises(ValueError,match='terbatas'):project.edit_clip(pid,'clip_01',{'end':value})
    assert project._JOBS.empty() and project.load(pid)==before


@pytest.fixture
def isolated_project(monkeypatch,tmp_path):
    monkeypatch.setattr(project,'PROJECTS_DIR',tmp_path/'projects')
    monkeypatch.setattr(project,'_JOBS',queue.Queue())
    return project.create(str(tmp_path/'synthetic.mp4'),{'auto_render':True,'clip_count':10,'candidate_count':10,
                          'min_sec':1,'max_sec':12,'duration_preset':'custom','content_profile':'podcast',
                          'recipe':'manual','use_llm':False,'snap_silence':False})


@pytest.mark.parametrize('mode,expected', [('normal',[1,2,3,4,5]),('filtered',[2]),('banned',[])])
def test_pipeline_persists_top_five_and_manual_rank_six(monkeypatch,tmp_path,isolated_project,mode,expected):
    p=isolated_project
    assert project._JOBS.get_nowait()[0]=='pipeline'
    monkeypatch.setattr(project.download,'fetch',lambda *a,**kw:(tmp_path/'synthetic.mp4','Synthetic'))
    monkeypatch.setattr(media,'probe',lambda *a:media.Probe(120,640,360,24,False))
    monkeypatch.setattr(media,'visual_activity',lambda *a:None)
    monkeypatch.setattr(project,'_activity',lambda *a:{})
    moments=[{'start':i*10,'end':i*10+8,'title':f'Point {i+1}','text':f'Point {i+1}. Clear explanation.'} for i in range(10)]
    monkeypatch.setattr(highlights,'find_moments',lambda *a,**kw:copy.deepcopy(moments))
    def ranked(items,*args):
        return [{**item,'rank':i+1,'score':90 if mode!='filtered' or i==1 or i>=5 else 10,
                 'banned':mode=='banned' and i<5,'pinned':i==5} for i,item in enumerate(items)]
    monkeypatch.setattr(candidates,'rerank',ranked)
    project._pipeline(p['id'])
    saved=project.load(p['id'])
    assert [c['rank'] for c in saved['candidates'] if c['status']=='queued']==expected
    assert all(c['status']=='draft_candidate' and not c.get('selected') for c in saved['candidates'][5:])
    assert project._JOBS.qsize()==len(expected)
    if not expected:assert saved['status']=='candidates_ready'
    while not project._JOBS.empty():
        kind,pid,extra=project._JOBS.get_nowait()
        assert kind=='render'
        project._set_clip(pid,extra['cid'],status='done')
    if expected:
        project._finish_renders(p['id'])
        assert project.load(p['id'])['status']=='done'
    sixth=saved['candidates'][5]['id']
    project.select_candidates(p['id'],[sixth])
    manual=project.batch_render(p['id'])
    assert next(c for c in manual['candidates'] if c['id']==sixth)['status']=='queued'
    assert project._JOBS.get_nowait()[2]['cid']==sixth


def test_batch_preflight_rejects_invalid_set_without_partial_queue(isolated_project):
    pid=isolated_project['id']
    project._JOBS.get_nowait()
    project.update(pid,media={'duration':30},candidates=[
        {'id':'good','start':0,'end':10,'status':'draft_candidate'},
        {'id':'bad','start':20,'end':40,'status':'draft_candidate'}])
    with pytest.raises(ValueError,match='durasi sumber'):project.batch_render(pid,['good','bad'])
    assert project._JOBS.empty()
    assert all(c['status']=='draft_candidate' for c in project.load(pid)['candidates'])


def test_preflight_http_report_does_not_start_workers(monkeypatch,isolated_project):
    from fastapi.testclient import TestClient
    from clipper import server
    p=isolated_project
    project.update(p['id'],media={'duration':30},candidates=[{'id':'c','start':0,'end':5,'status':'draft_candidate'}])
    monkeypatch.setattr(project,'start_worker',lambda:pytest.fail('Read-only test must not start workers'))
    client=TestClient(server.app)
    response=client.get(f'/api/projects/{p["id"]}/clips/c/preflight',headers={'Host':'127.0.0.1:8765'})
    assert response.status_code==200
    assert response.json()['can_render']
    assert client.get(f'/api/projects/{p["id"]}/clips/missing/preflight',headers={'Host':'127.0.0.1:8765'}).status_code==404


@pytest.mark.parametrize('start,end', [(1.01,3),(0,1.99)])
def test_cut_near_word_edges_is_still_reported(start,end):
    result=preflight.analyze({'start':start,'end':end},10,[{'w':'penting','s':1,'e':2}])
    assert any('memotong kata' in w for w in result['warnings'])


def test_exact_word_edges_do_not_warn_about_cut_words():
    result=preflight.analyze({'start':1,'end':2},10,[{'w':'utuh','s':1,'e':2}])
    assert not any('memotong kata' in w for w in result['warnings'])


def test_boundary_suggestion_preserves_words_without_mutation():
    clip={'start':1.1,'end':3.9}
    words=[{'w':'awal','s':1,'e':1.4},{'w':'akhir','s':3.7,'e':4.2}]
    before=copy.deepcopy((clip,words))
    result=preflight.analyze(clip,10,words)
    assert result['boundary_suggestion']=={'start':1.0,'end':4.2,'requires_review':True,'reason':'Preserve complete boundary words'}
    assert (clip,words)==before


def test_out_of_order_and_overlapping_captions_are_reported():
    words=[{'w':'dua','s':2,'e':3},{'w':'satu','s':1,'e':2.2}]
    result=preflight.analyze({'start':0,'end':4},10,words)
    assert any('tidak meningkat' in w for w in result['warnings'])
    assert any('tumpang tindih' in w for w in result['warnings'])
    assert result['can_render']
