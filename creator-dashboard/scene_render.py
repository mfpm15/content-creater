"""Bounded renderer controls. Prose direction is never evaluated as code."""
from __future__ import annotations

import json
import math

CAMERAS = ('legacy', 'locked', 'push-in', 'pull-out', 'pan-left', 'pan-right', 'orbit')
LIGHTING = ('legacy', 'soft', 'dramatic')
TRANSITIONS = ('legacy', 'fade', 'cut', 'slide')


def validate(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - {'camera', 'lighting', 'transition', 'strength'}:
        raise ValueError('Kontrol render harus objek camera, lighting, transition, strength')
    result = {}
    for name, choices in (('camera', CAMERAS), ('lighting', LIGHTING), ('transition', TRANSITIONS)):
        item = value.get(name, 'legacy')
        if not isinstance(item, str) or item not in choices:
            raise ValueError(f'Kontrol render {name} tidak dikenal')
        result[name] = item
    strength = value.get('strength', .5)
    if type(strength) not in (int, float) or not 0 <= strength <= 1 or not math.isfinite(strength):
        raise ValueError('Kekuatan kamera harus angka 0–1')
    result['strength'] = strength
    return result


def camera_tween(scene: dict, selector: str) -> str:
    controls = validate(scene.get('renderControls', {}))
    camera, amount = controls['camera'], controls['strength']
    # Target the illustration only: title/subtitles retain their safe areas.
    begin, end = {'xPercent': 0, 'scale': 1, 'rotation': 0}, {'xPercent': 0, 'scale': 1, 'rotation': 0}
    if camera == 'push-in': end['scale'] = 1 + .15 * amount
    elif camera == 'pull-out': begin['scale'] = 1 + .15 * amount
    elif camera in ('pan-left', 'pan-right'):
        sign = -1 if camera == 'pan-left' else 1
        begin['xPercent'], end['xPercent'] = -sign * 4 * amount, sign * 4 * amount
    elif camera == 'orbit': begin['rotation'], end['rotation'] = -3 * amount, 3 * amount
    end.update(duration=scene['duration'], ease='none', immediateRender=False, force3D=False)
    return f'tl.fromTo({json.dumps(selector)}, {json.dumps(begin)}, {json.dumps(end)}, {scene["start"]});'


def entrance(scene: dict, selector: str, three: bool = False) -> str:
    transition = validate(scene.get('renderControls', {}))['transition']
    duration = min(.45 if three else .55, scene['duration'] / 3)
    begin = {'opacity': 0, 'scale': 1, 'xPercent': 0, 'filter': 'blur(0px)'}
    if transition == 'cut': begin['opacity'] = 1; duration = 0
    elif transition == 'slide': begin['xPercent'] = 8
    elif transition == 'legacy':
        # Only used when explicitly requested alongside other controls.
        begin.update(scale=1.08, filter='blur(14px)')
    end = {'opacity': 1, 'scale': 1, 'xPercent': 0, 'filter': 'blur(0px)',
           'duration': duration, 'ease': 'power3.out', 'immediateRender': False, 'force3D': False}
    return f'tl.fromTo({json.dumps(selector)}, {json.dumps(begin)}, {json.dumps(end)}, {scene["start"]});'


def exit_tween(scene: dict, selector: str) -> str:
    transition = validate(scene.get('renderControls', {}))['transition']
    duration = 0 if transition == 'cut' else min(.22, scene['duration'] / 3)
    props = {'opacity': 0, 'duration': duration, 'ease': 'power2.in'}
    if transition == 'slide': props['xPercent'] = -8
    return f'tl.to({json.dumps(selector)}, {json.dumps(props)}, {scene["end"] - duration});'


def lighting_filter(scene: dict) -> str:
    return {'legacy': '', 'soft': 'filter:brightness(1.15) contrast(.85)',
            'dramatic': 'filter:brightness(.82) contrast(1.35)'}[validate(scene.get('renderControls', {}))['lighting']]


# Called for every absolute-time draw, including suppressed and backwards seeks.
THREE_SCRIPT = '''
function applySceneControls(t) {
    const shot = shotControls.find(s => t >= s.start && t < s.end);
    const c = shot ? shot.controls : {};
    const u = shot ? Math.max(0, Math.min(1, (t-shot.start)/(shot.end-shot.start))) : 0;
    const a = c.strength ?? .5;
    camera.position.set(Math.sin(t*.25)*2, Math.cos(t*.2)*1.5, 15);
    if (c.camera && c.camera !== 'legacy') {
        camera.position.set(0, 0, 15);
        if (c.camera === 'push-in') camera.position.z = 15-3*a*u;
        if (c.camera === 'pull-out') camera.position.z = 15-3*a*(1-u);
        if (c.camera === 'pan-left') camera.position.x = (1-2*u)*2*a;
        if (c.camera === 'pan-right') camera.position.x = (2*u-1)*2*a;
        if (c.camera === 'orbit') {
            const angle = (u-.5)*.6*a;
            camera.position.set(Math.sin(angle)*15, 0, Math.cos(angle)*15);
        }
    }
    const lights = c.lighting === 'soft' ? [3, 2, 2] : c.lighting === 'dramatic' ? [.5, 6, 7] : [2, 4, 5];
    ambientLight.intensity = lights[0]; keyLight.intensity = lights[1]; rimLight.intensity = lights[2];
}
'''
