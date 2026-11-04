"""Bounded interpretation of mechanical scene directions; never executable prose."""
from __future__ import annotations

import hashlib
import json
import re

import scene_render

# Specific nouns first. These are object grammars, independent of visualFamily.
OBJECTS = (
    ('barrier', r'barrier|penghalang', 'block'),
    ('balance', r'balance scale|timbangan|seven.*weight', 'balance'),
    ('vault', r'vault|brankas', 'open-vault'),
    ('lock', r'lock pins?|pin kunci|shear|geser.*pin', 'shear'),
    ('anchor', r'anchor|angkur|jangkar', 'anchor'),
    ('mast', r'antenna|antena|\bmast\b|menara.*pulsa', 'pulse'),
    ('prism', r'prism|prisma', 'refract'),
    ('registry', r'registry|registri|index plates?|pelat indeks', 'register'),
    ('matrix', r'matrix|matriks', 'dock'),
    ('seal', r'seal|segel', 'stamp-seal'),
    ('bridge', r'bridge|jembatan|bypass|non.linear route', 'bypass'),
    ('wall', r'outer wall|tembok|internal node|node internal', 'activate'),
    ('aperture', r'aperture|apertur|optical|optik', 'scan'),
    ('sleeve', r'sleeve|selongsong|tungsten|exploit core', 'insert'),
    ('conduit', r'conduit|pneumatic|pneumatik|capsule|kapsul', 'travel'),
    ('modules', r'modules?|modul', 'interlock'),
    ('plate', r'plate|pelat|tactical stamp', 'stamp'),
    ('chain', r'chain link|steel link|rantai|konektor baja', 'tension'),
)
ACTIONS = (
    ('expand', r'expand.*inspect|technical inspection|membuka.*inspeksi|inspection|inspeksi'),
    ('block', r'block|slam|menghentikan|menghalang|membentur'),
    ('shear', r'shear|snap|patah|mematah'),
    ('anchor', r'anchor|deploy.*bolt|mengembang|menambat'),
    ('pulse', r'emit|puls|memancar'),
    ('open-vault', r'open|extract|membuka|ekstrak'),
    ('refract', r'refract|membias|merapikan.*vektor'),
    ('balance', r'balanc|menimbang|seimbang|ganjal'),
    ('bypass', r'bypass|melompat|melewati.*node'),
    ('dock', r'dock|engag|merapat'),
    ('register', r'register|registr|index'),
    ('stamp-seal', r'stamp.*seal|cap.*segel'),
    ('stamp', r'stamp|press|mengecap|dicap'),
    ('scan', r'scan|menyapu|memindai'),
    ('insert', r'insert|masuk|memasukkan'),
    ('travel', r'travel|mov|melaju|bergerak|berjalan'),
    ('interlock', r'interlock|lock.*sequen|mengunci'),
    ('tension', r'taut|tension|menegang|tarik'),
    ('activate', r'activ|aktif'),
)
COMPATIBLE = {
    'chain': {'tension'}, 'plate': {'stamp'}, 'modules': {'interlock','expand'},
    'aperture': {'scan'}, 'sleeve': {'insert'}, 'conduit': {'travel','block'},
    'lock': {'shear'}, 'anchor': {'anchor'}, 'mast': {'pulse'}, 'vault': {'open-vault'},
    'prism': {'refract'}, 'registry': {'register','insert'}, 'balance': {'balance'},
    'barrier': {'block'}, 'wall': {'activate'}, 'bridge': {'bypass','travel'},
    'matrix': {'dock'}, 'seal': {'stamp-seal','stamp'},
}
CAMERAS = {'locked','push-in','pull-out','track-left','track-right','overhead','oblique'}
TRANSITIONS = {'match-movement','closure','object-wipe','light-transfer'}


def _text(value):
    return str(value or '')[:2000].lower()


def interpret(scene: dict) -> dict | None:
    """Return None for nonmechanical scenes; recognized but unsupported actions fail review."""
    subject = _text(scene.get('directionSubject') or scene.get('subject'))
    visual = _text(scene.get('visual'))
    # Subject wins over secondary objects in an action/setting description.
    found = next((row for row in OBJECTS if re.search(row[1], subject)), None)
    if found is None:
        found = next((row for row in OBJECTS if re.search(row[1], visual)), None)
    if found is None:
        supporting=_text(scene.get('midground'))+' '+_text(scene.get('metaphor'))
        found=next((row for row in OBJECTS if re.search(row[1], supporting)),None)
    if found is None:
        return None
    obj, _, default_action = found
    action_text = _text(scene.get('action'))
    exact_action=action_text in {name for name,_ in ACTIONS}
    action = action_text if exact_action else next((name for name, pattern in ACTIONS if re.search(pattern, action_text)), default_action)
    if obj == 'seal' and action == 'stamp': action = 'stamp-seal'
    if obj == 'registry' and action == 'insert': action = 'register'
    issues = []
    if action not in COMPATIBLE[obj]:
        issues.append(f'Unsupported object/action: {obj}/{action}')
    # Default motion strings from legacy plans are not interpreted as instructions.
    generic = {'target-lock push-in','lateral route follow','three-quarter orbit','locked accumulation',
               'split converge','iris pull-back','drifting parallax','tunnel push-through','planar whip',
               'establish-focus-reveal','locked symmetrical reveal'}
    if action_text and not exact_action and action_text not in generic and not any(re.search(p, action_text) for _, p in ACTIONS):
        issues.append('Action direction is not supported by the bounded interpreter')
    camera_text = _text(scene.get('camera'))
    camera = 'locked'
    for name, pattern in [('overhead',r'overhead|atas'), ('pull-out',r'pull.?out|pull.?back|scale reveal|mundur'),
                          ('push-in',r'push|close|macro|maju'), ('track-left',r'pan.left|track.left|kiri'),
                          ('track-right',r'track|lateral|follow|kanan'), ('oblique',r'orbit|oblique|three.quarter')]:
        if re.search(pattern,camera_text): camera=name;break
    controls=scene_render.validate(scene.get('renderControls',{}))
    if controls.get('camera','legacy') != 'legacy':
        camera={'pan-left':'track-left','pan-right':'track-right','orbit':'oblique'}.get(controls['camera'],controls['camera'])
    transition_text=_text(scene.get('transition'))
    transition='match-movement'
    for name, pattern in [('closure',r'clos|tutup|mechanic'),('object-wipe',r'wipe|sapu'),('light-transfer',r'light|cahaya')]:
        if re.search(pattern,transition_text):transition=name;break
    if controls.get('transition','legacy') != 'legacy': transition=controls['transition']
    composition=_text(scene.get('composition'))
    layout='diagonal' if 'diagonal' in composition else 'offset-left' if re.search('left|kiri',composition) else 'offset-right' if re.search('right|kanan',composition) else 'center'
    setting=_text(scene.get('setting'))
    background=_text(scene.get('background'))
    foreground=_text(scene.get('foreground'))
    token=str(scene.get('continuityToken') or '')
    if token and not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',token):
        raise ValueError('continuityToken must be 1–64 letters, digits, underscore or hyphen')
    if not token:
        continuity=_text(scene.get('continuity'))
        if re.search(r'steel.link|chain.link|konektor baja|mata rantai',continuity):token='steel-link'
    count_match=re.search(r'\b([1-9]|1[0-2])\b',subject)
    count=int(count_match[1]) if count_match else 7 if re.search(r'\bseven\b|\btujuh\b',subject) else 2 if obj=='balance' else 1
    cue=scene.get('visualCueWord')
    cue_offset=max(0,scene['wordCues'][cue]['start']-scene['start']) if cue is not None else 0
    spec={
        'version':1,'count':count,'strength':controls.get('strength',.5),'cueOffset':cue_offset,'object':obj,'action':action,'camera':camera,'transition':transition,
        'layout':layout,'set':'blueprint' if re.search('blueprint|cetak biru',background+' '+setting) else 'chamber',
        'foreground':'rail' if re.search('rail|rel|conduit',foreground) else 'bench',
        'lighting':controls.get('lighting') if controls.get('lighting','legacy')!='legacy' else 'soft' if re.search('soft|lembut',_text(scene.get('lighting'))) else 'dramatic',
        'continuityToken':token,'issues':issues,
        'beats':{'anticipation':[.1,.25],'action':[.25,.65],'followThrough':[.65,.85]},
    }
    # Signatures represent drawing and motion inputs, not labels, IDs or narration.
    spec['structureSignature']=hashlib.sha256(json.dumps([obj,count,layout,spec['set'],spec['foreground']]).encode()).hexdigest()[:16]
    spec['motionSignature']=f'{action}:{camera}:{transition}'
    return spec


def audit(plan: dict) -> dict:
    specs=[interpret(s) for s in plan['scenes']]
    directed=[s for s in specs if s]
    issues=[{'scene':i,'reason':reason} for i,s in enumerate(specs) if s for reason in s['issues']]
    for i in range(2,len(specs)):
        three=specs[i-2:i+1]
        if all(three) and len({s['structureSignature'] for s in three})==1:
            issues.append({'scene':i,'reason':'Three consecutive scenes share the same drawing structure'})
    diversity=len({s['action'] for s in directed})/len(directed) if directed else 0
    if len(directed)>=10 and diversity<.7:issues.append({'reason':'Mechanical action diversity below 70 percent'})
    if len(directed)>=10 and len({s['camera'] for s in directed})<4:issues.append({'reason':'Long mechanical sequence needs at least four camera grammars'})
    bindings=[{'from':i,'to':i+1,'token':a['continuityToken']} for i,(a,b) in enumerate(zip(specs,specs[1:])) if a and b and a['continuityToken'] and a['continuityToken']==b['continuityToken']]
    return {'version':1,'continuityBindings':bindings,'directedScenes':len(directed),'totalScenes':len(specs),'issues':issues,
            'actionDiversity':len({s['action'] for s in directed})/len(directed) if directed else 0,
            'cameraGrammars':sorted({s['camera'] for s in directed}), 'specs':specs,
            'scope':'Bounded mechanical grammar; not semantic validation of arbitrary prose'}
