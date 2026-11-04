"""Original SVG mechanical primitives. Only trusted geometry enters this module."""
from __future__ import annotations

import html
import json


def rect(x,y,w,h,fill='#829bad',radius=12,extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="#97a6b6" stroke-width="3" {extra}/>'


def circle(x,y,r,fill='#829bad',extra=''):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="#97a6b6" stroke-width="3" {extra}/>'


def group(part,body):
    return f'<g data-part="{part}">{body}</g>'


def bolts(x,y,w,h):
    return ''.join(circle(a,b,10,'#19212b')+f'<path d="M{a-5} {b}h10" stroke="#b5c1cc" stroke-width="2"/>' for a,b in ((x,y),(x+w,y),(x,y+h),(x+w,y+h)))


def plate(x=150,y=260,w=600,h=480):
    return rect(x,y,w,h)+rect(x+20,y+20,w-40,h-40,'#27323e',8)+bolts(x+35,y+35,w-70,h-70)


def capsule(x=280,y=420,w=340,h=160):
    return rect(x,y,w,h,'#e7ae57',h//2)+rect(x+w*.3,y+15,w*.2,h-30,'#293744',10)+f'<path d="M{x+45} {y+40}h{w*.15}" stroke="#ffe6b7" stroke-width="9" stroke-linecap="round"/>'


def chain_link(x=300,y=320,w=300,h=370):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w*.45}" fill="none" stroke="#1b222b" stroke-width="80"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w*.45}" fill="none" stroke="#a5bacb" stroke-width="56"/>'


def geometry(obj, count=1):
    """Compose reusable props; action code moves named parts, not whole slides."""
    if obj=='chain':
        return group('left',chain_link(150,250,250,380))+group('right',chain_link(500,370,250,380))+group('moving',chain_link(325,330,250,380))
    if obj in {'plate','seal'}:
        emblem=circle(450,570,130,'#28333d')+('<path d="M380 570l45 45 100-110" fill="none" stroke="#6baff5" stroke-width="30"/>' if obj=='seal' else '<path d="M370 580h160M450 500v160" stroke="#efb45a" stroke-width="20"/>')
        return plate(150,400,600,380)+group('reveal',emblem)+group('moving',rect(290,180,320,130)+rect(400,80,100,100,'#202b36')+rect(330,310,240,55,'#d3a052'))
    if obj=='modules':
        return ''.join(group(f'module-{i}',rect(270,115+i*110,360,92)+rect(300,140+i*110,300,18,'#344958',3)+rect(405,185+i*110,90,30,'#edb768',5)) for i in range(count))
    if obj=='aperture':
        lines=''.join(f'<path d="M180 {y}h540" stroke="#4a657c" stroke-width="2"/>' for y in range(250,751,65))
        return plate(120,220,660,560)+lines+group('moving',circle(450,440,180,'#202b36')+''.join(f'<path d="M450 440l150 -65 -20 150Z" fill="#607589" stroke="#b8c5d1" transform="rotate({i*60} 450 440)"/>' for i in range(6))+circle(450,440,72,'#78b4d0'))+group('beam','<path d="M180 650h540" stroke="#edba65" stroke-width="10"/>')
    if obj=='sleeve':
        return group('housing',rect(200,450,500,360,'#29343f')+rect(260,470,380,290,'#101821')+bolts(225,480,450,300))+group('moving',rect(300,160,300,420)+rect(320,190,260,160,'#e7ae57')+rect(350,600,200,75,'#d0a05a'))+group('latch',rect(180,650,120,65,'#6aaff0')+rect(600,650,120,65,'#6aaff0'))
    if obj=='conduit':
        return rect(90,230,720,110,'#202d39')+rect(90,660,720,110,'#202d39')+bolts(130,260,640,470)+group('moving',capsule())+group('trail',''.join(f'<path d="M{130+i*35} {460+i*30}h100" stroke="#e4b973" stroke-width="7"/>' for i in range(3)))
    if obj=='lock':
        return plate(140,200,620,600)+rect(180,420,540,180,'#111a23')+group('moving',rect(110,450,320,120,'#e7ae57'))+''.join(group(f'pin-{i}',rect(390+i*60,300,28,310,'#d1dbe2',8)) for i in range(5))+group('fragments',''.join(rect(390+i*60,530,28,80,'#d1dbe2',5) for i in range(5)))
    if obj=='anchor':
        return rect(130,280,640,550,'#333c44')+rect(330,300,240,500,'#18212a')+group('moving',rect(405,180,90,480)+rect(320,150,260,80))+group('left',rect(330,400,75,330,'#e5b465'))+group('right',rect(495,400,75,330,'#e5b465'))
    if obj=='mast':
        return plate(210,690,480,160)+group('moving',rect(405,230,90,470)+circle(450,200,70,'#e7ae57')+'<path d="M280 280l170-80 170 80" fill="none" stroke="#bbc9d3" stroke-width="20"/>')+''.join(group(f'pulse-{i}',f'<path d="M{330-i*70} {150-i*15}Q{270-i*90} 260 {330-i*70} {370+i*15}M{570+i*70} {150-i*15}Q{630+i*90} 260 {570+i*70} {370+i*15}" fill="none" stroke="#f1b75d" stroke-width="12"/>') for i in range(3))
    if obj=='vault':
        return plate(120,170,660,660)+rect(180,230,540,540,'#0c141d',30)+group('cartridges',''.join(rect(240+i*95,340,72,320,'#e7ae57',8) for i in range(4)))+group('moving',rect(180,230,540,540)+circle(450,500,170,'#283745')+circle(450,500,55)+''.join(f'<path d="M450 500v-135" stroke="#acbdcb" stroke-width="24" transform="rotate({i*60} 450 500)"/>' for i in range(6)))
    if obj=='prism':
        rays=''.join(f'<path d="M100 {270+i*85}L400 500" stroke="#dba951" stroke-width="8"/>' for i in range(6))
        outs=''.join(f'<path d="M520 500L800 {280+i*85}" stroke="#6aaff0" stroke-width="8"/>' for i in range(6))
        return group('left',rays)+group('right',outs)+group('moving','<path d="M450 180L670 780H230Z" fill="#41617a" fill-opacity=".8" stroke="#c5d9e7" stroke-width="10"/><path d="M450 180L450 640 230 780M450 640L670 780" fill="none" stroke="#91b9d8" stroke-width="5"/>')
    if obj=='registry':
        return plate(170,300,560,510)+''.join(rect(210,360+i*125,480,75,'#0d1823',4) for i in range(3))+''.join(group(f'card-{i}',rect(230,170+i*125,440,75)+'<path d="M270 '+str(205+i*125)+'h230" stroke="#e6b567" stroke-width="12"/>') for i in range(3))
    if obj=='balance':
        return '<path d="M450 360L570 810H330Z" fill="#4c6579" stroke="#bacbd8" stroke-width="5"/>'+rect(220,810,460,65)+group('beam','<path d="M140 430H760" stroke="#b5c7d6" stroke-width="28"/>'+circle(450,430,60,'#5f7c93')+'<path d="M165 430v230M735 430v230" stroke="#c5d0d9" stroke-width="8"/>'+rect(90,650,200,40)+rect(610,650,200,40)+''.join(rect(105+(i%3)*55,590-(i//3)*55,48,48,'#e7ae57',5) for i in range(count))+group('defense','<path d="M620 640L730 410 800 640Z" fill="#4d9fee" stroke="#c5e4ff" stroke-width="6"/>'))
    if obj=='barrier':
        return rect(120,730,660,90,'#40536a')+group('moving',rect(410,150,140,510,'#4d9fee',6)+rect(300,110,360,95))+group('capsule',capsule(120,550,280,150))+group('fragments','<path d="M360 580l80-55 10 80Z M340 650l60-30 20 100Z M430 640l80 15-60 70Z" fill="#dfac5b" stroke="#ffdd9a" stroke-width="4"/>')
    if obj=='wall':
        return group('housing',rect(160,190,580,620,'#34475a')+rect(220,250,460,500,'#141f2a')+bolts(190,220,520,560))+group('moving',circle(450,500,150,'#303e4d'))+group('reveal',circle(450,500,90,'#e7ae57'))
    if obj=='bridge':
        return '<path d="M100 720H800" stroke="#3e5162" stroke-width="60"/><path d="M100 720C180 170 720 170 800 720" stroke="#b6c9d8" stroke-width="28" fill="none"/>'+rect(360,620,180,140,'#263a4c')+group('moving',capsule(110,615,180,100))+group('reveal','<path d="M240 250h420" stroke="#69aff4" stroke-width="24"/>')
    if obj=='matrix':
        return plate(150,180,600,650)+''.join(group(f'cell-{i}',rect(210+(i%4)*130,250+(i//4)*130,100,100,'#20374e',5)) for i in range(16))+group('moving',rect(60,260,90,530,'#e7ae57',10)+''.join(rect(150,290+i*120,80,35,'#bbcbd6',3) for i in range(4)))
    raise ValueError(f'Unsupported mechanical object: {obj}')


def markup(spec: dict, index: int) -> str:
    prefix=f'op_{index}'
    body=geometry(spec['object'],spec['count']).replace('#METAL',f'#{prefix}_metal').replace('#AMBER',f'#{prefix}_amber')
    if spec['lighting']=='soft':body=body.replace('#829bad','#a1b5c5').replace('#27323e','#354858')
    spec_data=html.escape(json.dumps(spec,separators=(',',':')),quote=True)
    bg='<path d="M80 130H820V870H80Z M80 130L210 250H690L820 130M80 870L210 750H690L820 870" fill="#1c2732" stroke="#344657" stroke-width="6"/>'
    if spec['set']=='blueprint':
        bg+=''.join(f'<path d="M100 {n}H800M{n} 150V850" stroke="#38566b" stroke-width="2"/>' for n in range(150,801,100))
    foreground=('<path d="M60 830H840M60 890H840" stroke="#8296a8" stroke-width="28"/>' if spec['foreground']=='rail' else '<path d="M30 890L160 815H740L870 890V960H30Z" fill="#30404f" stroke="#60798e" stroke-width="6"/>')
    token=group('token','<path d="M-42 -20h84v40h-84Z" fill="none" stroke="#b9cbd8" stroke-width="18"/>') if spec['continuityToken'] else ''
    if spec['continuityToken']=='defense-wedge':
        token=group('token','<polygon data-part="token-shape" points="-60,60 0,-60 60,60 0,60" fill="#4d9fee" stroke="#c5e4ff" stroke-width="5"/>')
    return f'''<div class="visual-canvas-box directed-viz" data-directed="{spec_data}" data-family="directed" data-action="{spec['action']}" data-structure="{spec['structureSignature']}">
<svg shape-rendering="geometricPrecision" viewBox="0 0 900 1000" role="img" aria-label="{html.escape(spec['object'])}" xmlns="http://www.w3.org/2000/svg">
<defs><linearGradient id="{prefix}_metal" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#dce5ec"/><stop offset=".25" stop-color="#8197aa"/><stop offset=".55" stop-color="#344c62"/><stop offset=".8" stop-color="#9fb2c2"/><stop offset="1" stop-color="#456077"/></linearGradient>
<linearGradient id="{prefix}_amber"><stop stop-color="#af6f26"/><stop offset=".5" stop-color="#f5cb7c"/><stop offset="1" stop-color="#d2933e"/></linearGradient></defs>
<g class="scene-background">{bg}</g>
<g class="scene-midground"><g class="directed-camera"><g data-part="hero">{body}</g></g></g>
<g class="scene-foreground">{foreground}</g>
<g class="continuity-carrier" data-continuity="{html.escape(spec['continuityToken'])}">{token}</g>
<g class="mechanical-shutter"><path data-shutter="left" d="M0 0H450V1000H0Z" fill="#344b5d"/><path data-shutter="right" d="M450 0H900V1000H450Z" fill="#273c4e"/></g>
</svg></div>'''


CSS = '''
.directed-viz{max-height:none;height:100%;border:0;border-radius:0;background:transparent;overflow:hidden}
.directed-viz>svg{width:100%;height:100%;max-width:100%;max-height:100%;overflow:visible}
.directed-viz .scene-midground{transform-box:fill-box}
.family-directed .visual-wrapper{padding:0}
.family-directed .content-stack{grid-template-rows:minmax(0,18%) minmax(0,1fr)}
.family-directed .hero-title{line-height:1.15;background:none;-webkit-text-fill-color:#e1e8ef;text-shadow:none;letter-spacing:-.025em}
.family-directed .chapter-badge{background:#243240;border-color:#698298;color:#c5d2de;box-shadow:none}
.family-directed .badge-dot{background:#edb86a;box-shadow:none}
'''
