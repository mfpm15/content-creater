"""Self-contained Lottie subset: exported data is also the preview's only source."""
import scene_diagram
import json
import textwrap
import creative_profile


def build(plan: dict, aspect: dict) -> dict:
    width, height, fps = aspect['width'], aspect['height'], 30
    layers = []
    colors = [[.13,.83,.93,1], [.55,.36,.96,1], [.98,.75,.14,1]]
    kit=creative_profile.brand(plan['brand']) if plan.get('brand') else None
    rgb=lambda value:[int(value[i:i+2],16)/255 for i in (1,3,5)]
    font=kit['font'] if kit else 'Arial'
    if kit:colors=[rgb(kit['accent'])+[1]]*3
    for index, scene in enumerate(plan['scenes']):
        end = round(scene['end']*fps)
        start = min(end-1, round(creative_profile.reveal(scene)*fps))
        ramp = min(6, (end-start)/3)
        opacity = {'a':1, 'k':[{'t':start,'s':[0]},{'t':start+ramp,'s':[100]}, {'t':end-ramp,'s':[100]},{'t':end,'s':[0]}]}
        transform = {'o':opacity, 'r':{'a':0,'k':0}, 'p':{'a':0,'k':[width*.5,height*.4,0]},
                     'a':{'a':0,'k':[0,0,0]}, 's':{'a':1,'k':[{'t':start,'s':[85,85,100]},{'t':min(start+15,end),'s':[100,100,100]}]}}
        shape = {'ty':'rc' if scene.get('type') in {'data','compare','steps'} else 'el',
                 'p':{'a':0,'k':[0,0]}, 's':{'a':0,'k':[width*.45,min(width,height)*.35]}, 'r':{'a':0,'k':24}}
        layers.append({'ddd':0,'ind':len(layers)+1,'ty':4,'nm':scene['id'],'ip':start,'op':end,'st':0,
                       'ks':transform,'shapes':[shape,{'ty':'fl','c':{'a':0,'k':colors[index%3]},'o':{'a':0,'k':100},'r':1}]})
        size = round(min(width*.065,height*.055))
        title = str(scene.get('onScreenText') or scene.get('subject') or '')
        while True:
            lines=textwrap.wrap(title,width=max(8,int(width*.72/(size*.65)))) or ['']
            if len(lines)*size*1.25 <= height*.18 or size <= min(width,height)*.018:break
            size-=1
        text='\r'.join(lines)
        layers.append({'ddd':0,'ind':len(layers)+1,'ty':5,'nm':scene['id']+'-title','ip':start,'op':end,'st':0,
                       'ks':{**transform,'p':{'a':0,'k':[width*.46,height*.15,0]},'s':{'a':0,'k':[100,100,100]}},
                       't':{'d':{'k':[{'t':0,'s':{'t':text,'f':font,'s':size,'j':2,'tr':0,'lh':size*1.25,'fc':rgb(kit['text']) if kit else [1,1,1]}}]},'a':[]}})
        if 'diagram' in scene:
            diagram=scene_diagram.validate(scene['diagram'])
            layers[:]=[layer for layer in layers if layer['nm']!=scene['id']]
            process=diagram['kind']=='process'
            for j,label in enumerate(diagram['labels']):
                x=width*.46 if process else width*(.25+j*.42)
                y=height*(.39+j*.28/(len(diagram['labels'])-1)) if process else height*.5
                w=width*(.68 if process else .34)
                h=height*(.055 if process else .16)
                fs=min(width*.032,h*.35)
                label_lines=textwrap.wrap(label,width=max(8,int(w*.9/(fs*.65))))
                while len(label_lines)*fs*1.25>h*.85:
                    fs*=.9;label_lines=textwrap.wrap(label,width=max(8,int(w*.9/(fs*.65))))
                ks={**transform,'p':{'a':0,'k':[x,y,0]},'s':{'a':0,'k':[100,100,100]}}
                # Lottie front-to-back order: labels precede their backing plates.
                layers.append({'ddd':0,'ind':len(layers)+1,'ty':5,'nm':scene['id']+'-label-'+str(j),'ip':start,'op':end,'st':0,
                    'ks':{**ks,'p':{'a':0,'k':[x,y+fs*.3-(len(label_lines)-1)*fs*.625,0]}},
                    't':{'d':{'k':[{'t':0,'s':{'t':'\r'.join(label_lines),'f':font,'s':fs,'j':2,'tr':0,'lh':fs*1.25,'fc':rgb(kit['text']) if kit else [1,1,1]}}]},'a':[]}})
                layers.append({'ddd':0,'ind':len(layers)+1,'ty':4,'nm':scene['id']+'-node-'+str(j),'ip':start,'op':end,'st':0,
                    'ks':ks,'shapes':[{'ty':'rc','p':{'a':0,'k':[0,0]},'s':{'a':0,'k':[w,h]},'r':{'a':0,'k':min(16,h*.2)}},
                    {'ty':'fl','c':{'a':0,'k':[.09,.17,.24,1]},'o':{'a':0,'k':100},'r':1}]})
    if kit:
        transform={'o':{'a':0,'k':100},'r':{'a':0,'k':0},'p':{'a':0,'k':[width/2,height/2,0]},'a':{'a':0,'k':[0,0,0]},'s':{'a':0,'k':[100,100,100]}}
        layers.append({'ddd':0,'ind':len(layers)+1,'ty':4,'nm':'brand-background','ip':0,'op':round(plan['duration']*fps),'st':0,'ks':transform,
                       'shapes':[{'ty':'rc','p':{'a':0,'k':[0,0]},'s':{'a':0,'k':[width,height]},'r':{'a':0,'k':0}},{'ty':'fl','c':{'a':0,'k':rgb(kit['background'])+[1]},'o':{'a':0,'k':100},'r':1}]})
        if kit['wordmark']:
            layers.insert(0,{'ddd':0,'ind':len(layers)+1,'ty':5,'nm':'brand-wordmark','ip':0,'op':round(plan['duration']*fps),'st':0,
                'ks':{**transform,'p':{'a':0,'k':[width/2,height*.05,0]}},
                't':{'d':{'k':[{'t':0,'s':{'t':kit['wordmark'],'f':font,'s':min(24,width*.04),'j':2,'lh':28,'fc':rgb(kit['text'])}}]},'a':[]}})
    for layer_index, layer in enumerate(layers,1):
        layer['ind']=layer_index
        if layer['ty'] == 5:
            layer['t']['m'] = {'g':1, 'a':{'a':0, 'k':[0,0]}}
        for prop in layer['ks'].values():
            if prop.get('a'):
                for key in prop['k']:
                    key.update(i={'x':[.667],'y':[.667]},o={'x':[.333],'y':[.333]})
    return {'v':'5.12.2','fr':fps,'ip':0,'op':round(plan['duration']*fps),'w':width,'h':height,'nm':plan['topic'],
            'ddd':0,'assets':[],'fonts':{'list':[{'fName':font,'fFamily':font,'fStyle':'Regular','ascent':75}]},
            'layers':layers,'markers':[], 'meta':{'adapter':'local-vector-v1','scope':'ellipse/rectangle/text/linear-transforms',
                                               'limitations':['No audio','No 3D or external assets','Visual prompts simplified to vector primitives']}}


def preview(animation: dict) -> str:
    serialized = json.dumps(animation, ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Preview Lottie</title>
<style>body{margin:0;background:#101426;color:white;font-family:Arial;height:100vh;display:grid;grid-template-rows:1fr auto}svg{height:100%;width:100%;min-height:0}footer{padding:10px;display:flex;gap:10px;align-items:center}input{flex:1}</style>
<svg id="stage" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Preview data Lottie yang diekspor"></svg><footer><button id="play">Putar</button><input id="seek" type="range" min="0" value="0" aria-label="Frame"><span id="time"></span></footer>
<script id="animation" type="application/json">''' + serialized + '''</script><script>
const data=JSON.parse(document.getElementById('animation').textContent), svg=document.getElementById('stage'), seek=document.getElementById('seek');
svg.setAttribute('viewBox',`0 0 ${data.w} ${data.h}`);seek.max=data.op-1;
const NS='http://www.w3.org/2000/svg';
function property(p,f){if(!p)return 0;if(!p.a)return p.k;const keys=p.k;let i=0;while(i+1<keys.length&&keys[i+1].t<=f)i++;const a=keys[i],b=keys[Math.min(i+1,keys.length-1)],v=a.s;if(a===b||a.h)return v;const t=Math.max(0,Math.min(1,(f-a.t)/Math.max(1,b.t-a.t)));return v.map((x,j)=>x+((b.s[j]??x)-x)*t)}
function scalar(p,f){const v=property(p,f);return Array.isArray(v)?v[0]:v}
function element(tag,attrs){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));return n}
function draw(f){svg.replaceChildren();for(const layer of [...data.layers].reverse()){if(f<layer.ip||f>=layer.op)continue;const pos=property(layer.ks.p,f),scale=property(layer.ks.s,f);const g=element('g',{transform:`translate(${pos[0]} ${pos[1]}) rotate(${scalar(layer.ks.r,f)}) scale(${scale[0]/100} ${scale[1]/100})`,opacity:scalar(layer.ks.o,f)/100});
if(layer.ty===4){const shape=layer.shapes.find(s=>['el','rc'].includes(s.ty)),fill=layer.shapes.find(s=>s.ty==='fl'),sz=property(shape.s,f),c=property(fill.c,f),color=`rgb(${c.slice(0,3).map(n=>Math.round(n*255)).join(',')})`;g.append(shape.ty==='el'?element('ellipse',{cx:0,cy:0,rx:sz[0]/2,ry:sz[1]/2,fill:color}):element('rect',{x:-sz[0]/2,y:-sz[1]/2,width:sz[0],height:sz[1],rx:scalar(shape.r,f),fill:color}));}
if(layer.ty===5){const d=layer.t.d.k[0].s,text=element('text',{'text-anchor':'middle','font-family':d.f,'font-size':d.s,fill:`rgb(${d.fc.map(n=>Math.round(n*255)).join(',')})`});d.t.split('\\r').forEach((line,i)=>{const span=element('tspan',{x:0,y:i*d.lh});span.textContent=line;text.append(span)});g.append(text)}svg.append(g)}seek.value=f;document.getElementById('time').textContent=(f/data.fr).toFixed(1)+'s'}
let playing=false,frame=0,previous=performance.now();function tick(now){if(playing)frame=(frame+(now-previous)*data.fr/1000)%data.op;previous=now;draw(frame);requestAnimationFrame(tick)}
seek.oninput=()=>{frame=Number(seek.value);draw(frame)};document.getElementById('play').onclick=event=>{playing=!playing;event.target.textContent=playing?'Jeda':'Putar'};
window.__lottiePreview={data,seek:f=>{playing=false;frame=f;draw(f)}};requestAnimationFrame(tick);
</script></html>'''
