import json
from clipper import project


def test_workspace_edits_feed_render_words_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr(project, 'pdir', lambda pid: tmp_path)
    state = {'settings': {}, 'clips': [{'status': 'done'}]}
    monkeypatch.setattr(project, 'load', lambda pid: state)
    monkeypatch.setattr(project, 'save', lambda value: None)
    (tmp_path / 'transcript.json').write_text(json.dumps({'words': [{'w': 'salah', 's': 0, 'e': 1}]}))
    initial = project.load_caption_workspace('p')
    project.save_caption_workspace('p', {'cues': [{'start': 0, 'end': 1, 'text': 'Stuxnet'}]}, initial['revision'])
    assert project.resolve_caption_track('p')[0]['w'] == 'Stuxnet'
    assert state['clips'][0]['needs_rerender']
    undone = project.caption_action('p', 'undo', {})
    assert undone['redo_stack']
    assert project.resolve_caption_track('p')[0]['w'] == 'salah'
    project.caption_action('p', 'redo', {})
    assert project.resolve_caption_track('p')[0]['w'] == 'Stuxnet'


def test_dominant_mouth_activity_selects_single_speaker():
    from clipper import shots
    info = [{'faces': [(0.25, 0.14, 3.0), (0.75, 0.14, 0.05)],
             'boxes': [(0.25, 0.4, 0.14, 0.25), (0.75, 0.4, 0.14, 0.25)]} for _ in range(12)]
    result = shots.classify(info, 0, 4, 1920, 1080)
    assert result['mode'] == 'single'
    assert result['reason'] == 'sustained-mouth-activity'


def test_local_provider_credentials_are_redacted():
    from clipper.security import register_secrets, redact
    register_secrets(['local-config-test-credential'])
    assert 'local-config-test-credential' not in redact('Error: local-config-test-credential')
