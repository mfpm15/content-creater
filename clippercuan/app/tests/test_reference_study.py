import subprocess

import pytest

from clipper import reference_study
from clipper.config import FFMPEG


def test_local_scene_measurements_distinguish_tempo_from_story(tmp_path):
    path=tmp_path/'reference.mp4'
    subprocess.run([FFMPEG,'-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=10:d=1',
                    '-f','lavfi','-i','color=c=blue:s=320x180:r=10:d=1','-filter_complex',
                    '[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-c:v','libx264',str(path)],check=True)
    result=reference_study.analyze(path,[{'w':'Kenapa?','s':0,'e':.3},{'w':'Contoh','s':1,'e':1.3}],2,seconds=2)
    assert result['shots']==2 and result['cuts_relative_seconds']==pytest.approx([1],abs=.11)
    assert result['words_per_second']==1
    assert result['transcript_pauses']==[{'start':.3,'end':1}]
    assert 'question' in result['hook']['archetypes']
    assert any('unmeasured' in note for note in result['manual_review'])
    assert result['transcript_status']=='available'
    assert sum(part['cuts'] for part in result['timeline_thirds'])==1
    for start,seconds in [(0,121),(-1,5),(2,1)]:
        with pytest.raises(ValueError):reference_study.analyze(path,[],2,start,seconds)


def test_timeline_preserves_offsets_counts_and_overlapping_timestamp_coverage():
    words=[{'s':10,'e':12,'w':'Tidak'},{'s':11,'e':13,'w':'3'},
           {'s':13,'e':13.5,'w':'kali'},{'s':15.5,'e':16,'w':'akhir'}]
    parts=reference_study._timeline(words,[1,2,5.5],10,16)
    assert [part['start_relative_seconds'] for part in parts]==[0,2,4]
    assert [part['cuts'] for part in parts]==[1,1,1]
    assert parts[0]['transcript_coverage_percent']==100
    assert parts[1]['transcript_coverage_percent']==75
    assert parts[1]['excerpt']=='kali'
    assert parts[2]['transcript_coverage_percent']==25
    empty=reference_study._timeline([],[],10,16)
    assert all(part['words_per_second'] is None and part['transcript_coverage_percent'] is None for part in empty)
