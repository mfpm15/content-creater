"""Measured libass/FFmpeg exports and fail-closed artifact downloads."""
import copy
import queue
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clipper import caption_geometry, captions, delivery, platform_export, project, media
from clipper.config import DEFAULTS, FFMPEG, deep_merge
from clipper.server import app

HAS_FFMPEG = bool(shutil.which(FFMPEG) or Path(FFMPEG).exists())


@pytest.fixture
def clip_state(monkeypatch, tmp_path):
    clip = {'id': 'clip_01', 'status': 'done', 'file': 'clip_01.mp4',
            'ass': 'subtitles/clip_01.ass', 'version': 1, 'start': 0, 'end': 1}
    state = {'id': 'example', 'clips': [clip], 'candidates': [clip], 'settings': {}}
    monkeypatch.setattr(project, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(project, 'load', lambda pid: copy.deepcopy(state))
    def save(value):
        state.clear()
        state.update(copy.deepcopy(value))
    monkeypatch.setattr(project, 'save', save)
    monkeypatch.setattr(project, '_JOBS', queue.Queue())
    return state, tmp_path


def fixture_media(folder, y=50):
    source = folder / 'clip_01.mp4'
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'color=c=navy:s=320x568:r=10:d=1',
                    '-f', 'lavfi', '-i', 'sine=f=600:d=1', '-shortest',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-metadata', 'comment=private-source-tag', str(source)], check=True)
    subs = folder / 'subtitles'
    subs.mkdir(exist_ok=True)
    cfg = deep_merge(DEFAULTS, {'caption': {'enabled': True, 'y_pct': y, 'animation': 'pop', 'box': True},
                                'title': {'enabled': False}, 'watermark': {'enabled': False}})
    words = [{'w': 'Hello', 's': 0, 'e': .45}, {'w': 'world', 's': .45, 'e': .95}]
    (subs / 'clip_01.ass').write_text(captions.build_ass(words, '', cfg, (320, 568), 1), 'utf-8')
    return source


@pytest.mark.skipif(not HAS_FFMPEG, reason='FFmpeg unavailable')
def test_measured_variant_and_download_detect_tampering(clip_state):
    state, folder = clip_state
    source = fixture_media(folder)
    state['clips'][0].update(artifact_digest=media.file_digest(source), caption_ass_digest=media.file_digest(folder / 'subtitles/clip_01.ass'))
    before = source.read_bytes()
    entry = platform_export.enqueue('example', 'clip_01', 'shorts')
    assert platform_export.enqueue('example', 'clip_01', 'shorts')['token'] == entry['token']
    assert project._JOBS.qsize() == 1
    with pytest.raises(platform_export.ExportBlocked):
        platform_export.download('example', 'clip_01', 'shorts')
    platform_export.process('example', 'clip_01', 'shorts', entry['token'])
    result = state['clips'][0]['exports']['shorts']
    assert result['status'] == 'passed', result
    assert result['geometry']['method'] == 'libass_alpha_bbox_all_frames'
    assert result['geometry']['ok']
    assert abs(result['delivery']['measured']['lufs'] + 14) <= 2
    assert result['delivery']['spec_verified_official'] is False
    output = platform_export.download('example', 'clip_01', 'shorts')
    assert output.parent.name == 'variants'
    assert b'private-source-tag' not in output.read_bytes()
    assert source.read_bytes() == before
    output.write_bytes(b'tampered')
    with pytest.raises(platform_export.ExportBlocked, match='Artefak berubah'):
        platform_export.download('example', 'clip_01', 'shorts')


@pytest.mark.skipif(not HAS_FFMPEG, reason='FFmpeg unavailable')
def test_unsafe_caption_blocks_export_before_encoder(clip_state, monkeypatch):
    state, folder = clip_state
    source = fixture_media(folder, y=90)
    state['clips'][0].update(artifact_digest=media.file_digest(source), caption_ass_digest=media.file_digest(folder / 'subtitles/clip_01.ass'))
    called = []
    monkeypatch.setattr(platform_export, 'transcode', lambda *args: called.append(True))
    entry = platform_export.enqueue('example', 'clip_01', 'tiktok')
    platform_export.process('example', 'clip_01', 'tiktok', entry['token'])
    result = state['clips'][0]['exports']['tiktok']
    assert result['status'] == 'blocked'
    assert not result['geometry']['ok']
    assert not called
    assert not list(folder.glob('variants/*.mp4'))


def test_path_escape_and_stale_render_fail_closed(clip_state):
    state, _ = clip_state
    state['clips'][0]['needs_rerender'] = True
    with pytest.raises(platform_export.ExportBlocked):
        platform_export.enqueue('example', 'clip_01', 'tiktok')
    state['clips'][0]['needs_rerender'] = False
    state['clips'][0]['file'] = '../outside.mp4'
    with pytest.raises(platform_export.ExportBlocked):
        platform_export.enqueue('example', 'clip_01', 'tiktok')
    with pytest.raises(ValueError):
        platform_export.enqueue('example', 'clip_01', '../tiktok')
    assert project._JOBS.empty()


def test_bounds_use_platform_specific_edges():
    measured = {'status': 'measured', 'width': 1000, 'height': 1000,
                'bounds': {'left': 100, 'right': 870, 'top': 110, 'bottom': 800}}
    assert not caption_geometry.evaluate(measured, delivery.PLATFORMS['tiktok']['safe'])['ok']
    assert caption_geometry.evaluate(measured, delivery.PLATFORMS['shorts']['safe'])['ok']


def test_export_api_reports_blocked_and_bad_platform(clip_state):
    state, _ = clip_state
    client = TestClient(app)
    base = '/api/projects/example/clips/clip_01/exports'
    assert client.get(base + '/shorts').json()['status'] == 'not_started'
    assert client.get(base + '/shorts/download').status_code == 409
    assert client.post(base + '/unknown').status_code == 400
    state['clips'][0]['needs_rerender'] = True
    assert client.post(base + '/shorts').status_code == 409
    assert client.get('/files/example/variants%2Fguess.mp4').status_code == 404


def test_queued_source_changed_before_processing(clip_state):
    state, folder = clip_state
    source = folder / 'clip_01.mp4'
    source.write_bytes(b'original')
    state['clips'][0].update(artifact_digest=media.file_digest(source), caption_ass_digest='placeholder')
    entry = platform_export.enqueue('example', 'clip_01', 'reels')
    source.write_bytes(b'replaced')
    platform_export.process('example', 'clip_01', 'reels', entry['token'])
    assert state['clips'][0]['exports']['reels']['status'] == 'blocked'


def test_platform_export_preserves_authentication(clip_state, monkeypatch):
    from clipper import server
    monkeypatch.setattr(server, 'TOKEN', 'test-export-token')
    client = TestClient(app)
    base = '/api/projects/example/clips/clip_01/exports/shorts'
    assert client.get(base).status_code == 401
    assert client.post(base).status_code == 401
    assert client.get(base + '/download').status_code == 401
    response = client.get(base, headers={'Authorization': 'Bearer test-export-token'})
    assert response.status_code == 200
    assert 'test-export-token' not in response.text
    for origin in ('https://example.invalid', 'null', 'https://testserver'):
        assert client.post(base, headers={'Authorization': 'Bearer test-export-token', 'Origin': origin}).status_code == 403


def test_interrupted_variant_is_recoverable(clip_state, monkeypatch):
    import json
    state, folder = clip_state
    state['status'] = 'done'
    state['clips'][0]['exports'] = {'shorts': {'status': 'processing', 'owner': 0}}
    directory = folder / 'example'
    directory.mkdir()
    (directory / 'project.json').write_text(json.dumps(state), 'utf-8')
    monkeypatch.setattr(project, 'PROJECTS_DIR', folder)
    project.recover_interrupted()
    assert state['status'] == 'done'
    assert state['clips'][0]['exports']['shorts']['status'] == 'interrupted'


def test_desktop_build_carries_platform_data(monkeypatch):
    import os
    import runpy
    import sys
    import types
    args = []
    package = types.ModuleType('PyInstaller')
    main = types.ModuleType('PyInstaller.__main__')
    main.run = args.extend
    package.__main__ = main
    monkeypatch.setitem(sys.modules, 'PyInstaller', package)
    monkeypatch.setitem(sys.modules, 'PyInstaller.__main__', main)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'build.py'))
    profile_argument = next(a for a in args if a.startswith('--add-data=') and 'platform_specs.json' in a)
    source, destination = profile_argument[len('--add-data='):].rsplit(os.pathsep, 1)
    assert Path(source).is_file()
    assert destination == 'clipper'


def test_public_profiles_share_the_checked_spec():
    response = TestClient(app).get('/api/export-profiles')
    assert response.status_code == 200
    data = response.json()
    assert data['verified_official'] is False
    assert data['profiles']['tiktok']['safe'] == delivery.PLATFORMS['tiktok']['safe']
    assert set(data['profiles']) == set(delivery.PLATFORMS)


def test_delayed_cancellation_cannot_overwrite_completed_or_retried_work(clip_state):
    state, _ = clip_state
    project._CANCEL.add('example')
    try:
        state['status'] = 'done'
        assert not project.finish_cancellation('example')
        assert state['status'] == 'done'
        state['status'] = 'running'
        assert project.finish_cancellation('example')
        assert state['status'] == 'cancelled'
        state['status'] = 'queued'
        project._CANCEL.discard('example')  # retry removes the cancellation request
        assert not project.finish_cancellation('example')
        assert state['status'] == 'queued'
    finally:
        project._CANCEL.discard('example')


def test_only_changed_visual_settings_invalidate_exports(clip_state):
    state, _ = clip_state
    state['settings'] = {'caption': {'size': 84}}
    state['clips'][0]['exports'] = {'shorts': {'status': 'passed'}}
    project.update_settings('example', {'caption': {'size': 84}})
    assert not state['clips'][0].get('needs_rerender')
    assert state['clips'][0]['exports']['shorts']['status'] == 'passed'
    project.update_settings('example', {'caption': {'size': 85}})
    assert state['clips'][0]['needs_rerender']
    assert state['clips'][0]['exports'] == {}
