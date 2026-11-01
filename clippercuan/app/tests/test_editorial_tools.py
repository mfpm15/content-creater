import math
import wave
import struct

import numpy as np
import pytest

from clipper import silence, editorial, cursor, shots, facetrack


def test_snap_preserves_words_and_duration_constraints():
    words = [{'w':'a', 's':1, 'e':1.3}, {'w':'b', 's':1.4, 'e':1.9}, {'w':'next', 's':3, 'e':3.4}]
    result = silence.snap(1, 2, words, [[.4,.8],[2,2.4]], 4, 1, 2)
    assert result['changed']
    assert result['start'] <= 1 and result['end'] >= 1.9
    assert result['end'] < 3
    assert 1 <= result['end']-result['start'] <= 2
    original = silence.snap(1,2,words,[[0,3]],4,1,1.1)
    assert original['start'] == 1 and original['end'] == 2


def test_detect_real_silence_and_cache(tmp_path):
    path = tmp_path/'voice.wav'
    with wave.open(str(path),'wb') as target:
        target.setparams((1,2,16000,0,'NONE','not compressed'))
        target.writeframes(b''.join(struct.pack('<h', int(4000*math.sin(i/16000*440*2*math.pi)) if 16000<=i<32000 else 0) for i in range(48000)))
    detected = silence.detect(path,3,tmp_path/'silence.json')
    assert detected[0][0] == 0 and detected[0][1] == pytest.approx(1, abs=.05)
    assert detected[-1][0] == pytest.approx(2, abs=.05)
    assert silence.detect(path,3,tmp_path/'silence.json') == detected


def timed_words(text):
    return [{'w':word, 's':i*.3, 'e':i*.3+.25} for i,word in enumerate(text.split())]


def test_exact_retakes_preserve_numbers_and_negation():
    exact = editorial.retakes(timed_words('Saya pilih tiga cara ini. Saya pilih tiga cara ini.'))
    assert exact['suggestions'][0]['apply_allowed']
    changed = editorial.retakes(timed_words('Saya tidak pilih 3 cara ini. Saya pilih 4 cara ini.'))
    assert not any(s['apply_allowed'] for s in changed['suggestions'])
    assert editorial.words_revision(timed_words('a')) != editorial.words_revision(timed_words('b'))


def test_hook_reports_literal_evidence_only():
    result = editorial.hook_archetypes('Saya pernah mencoba 3 cara, tapi kenapa gagal?')
    assert {'question','number','personal_experience','contrast'} <= set(result['archetypes'])
    assert result['evidence']['number'] == '3'
    assert editorial.hook_archetypes('Halo dunia')['archetypes'] == []


def test_cursor_ambiguity_keeps_full_frame_fallback():
    frames = np.zeros((12,100,160),dtype=np.uint8)
    assert cursor.track(frames,1920,1080)['fallback']
    for i in range(12):
        frames[i,40:48,10+i*4:14+i*4] = 255
    result = cursor.track(frames,1920,1080)
    assert result['confidence'] >= .6 and result['keys']


def test_audio_gated_turns_split_a_single_camera_shot():
    frames = []
    for i in range(12):
        frames.append({'faces':[(.25,.15,3 if i<6 else .02),(.75,.15,.02 if i<6 else 3)],
                       'boxes':[(.25,.4,.15,.2),(.75,.4,.15,.2)]})
    pieces = shots.speaker_pieces(frames,0,12/facetrack.SAMPLE_FPS,1920,1080,np.ones(12,dtype=bool))
    assert len(pieces) == 2 and all(p['mode']=='single' for p in pieces)
    assert [p['speaker_side'] for p in pieces] == [0,1]
    assert shots.speaker_pieces(frames,0,12/facetrack.SAMPLE_FPS,1920,1080,np.zeros(12,dtype=bool)) == []


def test_take_approval_rejects_stale_or_unconfirmed_and_preserves_other_words(monkeypatch):
    from clipper import server
    from fastapi import HTTPException
    words=timed_words('Saya pilih tiga cara ini. Saya pilih tiga cara ini. Akhir cerita.')
    report=editorial.retakes(words)
    monkeypatch.setattr(server,'_clip_words_full',lambda *args:(None,None,words))
    with pytest.raises(HTTPException) as error:
        server.apply_take('p','c',server.TakeApproval(revision='stale',index=0,talking_head=True))
    assert error.value.status_code==409
    with pytest.raises(HTTPException) as error:
        server.apply_take('p','c',server.TakeApproval(revision=report['revision'],index=0))
    assert error.value.status_code==400
    calls=[]
    monkeypatch.setattr(server.project,'edit_clip',lambda *args,**kwargs:calls.append((args,kwargs)))
    monkeypatch.setattr(server.project,'_set_clip',lambda *args,**kwargs:None)
    monkeypatch.setattr(server.project,'load',lambda pid:{'id':pid})
    server.apply_take('p','c',server.TakeApproval(revision=report['revision'],index=0,talking_head=True))
    changed=calls[0][0][2]
    assert changed['words']==words[5:]
    assert changed['overrides']['cut_silence'] and calls[0][1]['rerender']
