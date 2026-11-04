/* Original absolute-time choreography. No RAF, wall clock, RNG or previous-frame state. */
function createDirectedRenderer() {
    const clamp = v => Math.max(0, Math.min(1, v));
    const smooth = v => {v=clamp(v);return v*v*(3-2*v)};
    const shots = [...document.querySelectorAll('[data-directed]')].map(element => ({
        element, template:element.innerHTML, scene:element.closest('.scene'), spec:JSON.parse(element.dataset.directed),
        parts:[...element.querySelectorAll('[data-part]')],
        camera:element.querySelector('.directed-camera'),
        background:element.querySelector('.scene-background'),
        foreground:element.querySelector('.scene-foreground'),
        shutters:[...element.querySelectorAll('[data-shutter]')]
    }));
    const events=[];
    for (const shot of shots) {
        const start=Number(shot.scene.dataset.start), duration=Number(shot.scene.dataset.duration);
        events.push({t:start+duration*.65,type:'mechanical-hit',action:shot.spec.action});
    }
    window.EV=events; // Cue metadata only; no claim these sounds have been synthesized.
    return function drawDirectedScenes(t) {
        for (const shot of shots) {
            const {scene,element,spec}=shot;
            const start=Number(scene.dataset.start), duration=Number(scene.dataset.duration);
            const active=t>=start && t<start+duration;
            scene.style.visibility=active?'visible':'hidden';
            if (!active) continue;
            // Rebuild the small SVG drawing tree from its trusted source on each sample.
            // Retained SVG raster caches otherwise depend on the preceding seek path.
            element.innerHTML=shot.template;
            const parts=[...element.querySelectorAll('[data-part]')];
            const camera=element.querySelector('.directed-camera');
            const shutters=[...element.querySelectorAll('[data-shutter]')];
            shot.background=element.querySelector('.scene-background');
            shot.foreground=element.querySelector('.scene-foreground');
            const timeU=clamp((t-start)/duration);
            const u=clamp((t-start-spec.cueOffset)/Math.max(.01,duration-spec.cueOffset));
            const anticipation=smooth((u-.1)/.15), a=smooth((u-.25)/.4);
            scene.querySelector('.hero-title').style.opacity=t<start+spec.cueOffset?'0':'1';
            const f=clamp((u-.65)/.2), recoil=Math.sin(f*Math.PI*3)*Math.exp(-f*5)*(u>=.65?1:0);
            const part=name=>parts.filter(p=>p.dataset.part===name);
            const set=(name,transform='',opacity=1)=>part(name).forEach(p=>{
                p.setAttribute('transform',transform);p.setAttribute('opacity',String(opacity));
            });
            // Reset every mutable attribute on each sample, including reverse seeks.
            for (const p of parts) {p.setAttribute('transform','');p.setAttribute('opacity','1')}
            const stretch=({plate:1.65,seal:1.65,registry:1.5,bridge:1.65,modules:1,mast:1,wall:1.1,vault:1.1,matrix:1.1})[spec.object]||1.3;
            set('hero',`translate(${spec.layout==='offset-left'?-60:spec.layout==='offset-right'?60:0} 0) rotate(${spec.layout==='diagonal'?-7:0} 450 500) translate(450 500) scale(1 ${stretch}) translate(-450 -500)`);
            switch(spec.action) {
                case 'tension':
                    set('left',`translate(${-45*a+12*anticipation+recoil*8} ${20*(1-a)}) rotate(${-8*(1-a)} 300 450)`);
                    set('right',`translate(${45*a-12*anticipation-recoil*8} ${-20*(1-a)}) rotate(${8*(1-a)} 600 550)`);
                    set('moving',`rotate(${12*(1-a)+recoil*3} 450 500)`); break;
                case 'stamp': case 'stamp-seal':
                    set('moving',`translate(0 ${-35*anticipation*(1-a)+200*a-22*smooth(f)+recoil*6})`);
                    set('reveal','',smooth((u-.6)/.1));break;
                case 'interlock':
                    for(let i=0;i<spec.count;i++) {
                        const p=smooth((u-.18-i*.045)/.27);
                        set(`module-${i}`,`translate(${(i%2?1:-1)*(1-p)*190} ${-(1-p)*45+recoil*2})`);
                    } break;
                case 'expand':
                    for(let i=0;i<spec.count;i++)set(`module-${i}`,`translate(${(i%2?1:-1)*a*95} ${(i-3)*a*12}) rotate(${(i%2?1:-1)*a*7} 450 ${160+i*110})`);
                    break;
                case 'scan':
                    set('moving',`translate(${120*Math.sin(a*Math.PI)-15*anticipation*(1-a)} ${180*a})`);
                    set('beam',`translate(0 ${-330+330*a})`,.2+.8*anticipation);break;
                case 'insert':
                    set('moving',`translate(0 ${-90-30*anticipation*(1-a)+230*a+recoil*3})`);
                    set('latch',`translate(0 ${35*(1-smooth((u-.6)/.13))})`);break;
                case 'travel':
                    set('moving',`translate(${-160-30*anticipation*(1-a)+340*a+recoil*6} 0)`);
                    set('trail',`translate(${340*a-200} 0)`,Math.sin(a*Math.PI)*.7);break;
                case 'shear':
                    set('moving',`translate(${-30*anticipation*(1-a)+190*a+recoil*5} 0)`);
                    for(let i=0;i<5;i++){set(`pin-${i}`,`rotate(${a*10} ${404+i*60} 300)`);part(`pin-${i}`)[0].querySelector('rect').setAttribute('height',String(310-80*smooth((u-.55)/.06)))}
                    set('fragments',`translate(${110*smooth((u-.57)/.22)} ${95*smooth((u-.57)/.22)}) rotate(${22*smooth((u-.57)/.22)} 500 650)`,smooth((u-.55)/.06));break;
                case 'anchor':
                    set('moving',`translate(0 ${-50*(1-a)-20*anticipation*(1-a)+recoil*3})`);
                    set('left',`rotate(${a*17} 370 400)`);set('right',`rotate(${-a*17} 530 400)`);break;
                case 'pulse':
                    set('moving',`translate(0 ${150*(1-a)+recoil*3})`);
                    for(let i=0;i<3;i++)set(`pulse-${i}`,`translate(450 260) scale(${.85+.15*smooth((u-.4-i*.1)/.18)}) translate(-450 -260)`,smooth((u-.4-i*.1)/.18));break;
                case 'open-vault':
                    set('moving',`translate(180 0) scale(${1-.88*a} 1) translate(-180 0)`);
                    set('cartridges',`translate(${60*smooth((u-.6)/.22)} ${-40*smooth((u-.6)/.22)})`);break;
                case 'refract':
                    set('moving',`rotate(${-8*(1-a)+recoil*2} 450 500)`);
                    set('left','',.25+.75*anticipation);set('right','',smooth((u-.35)/.3));break;
                case 'register':
                    for(let i=0;i<3;i++)set(`card-${i}`,`translate(0 ${190*smooth((u-.22-i*.09)/.25)})`);
                    break;
                case 'balance':
                    set('beam',`rotate(${-12+27*a+recoil*3} 450 430)`);
                    set('defense',`translate(0 ${-260*(1-a)-25*anticipation*(1-a)})`);break;
                case 'block':
                    set('moving',`translate(0 ${-90*anticipation*(1-a)+160*a+recoil*8})`);
                    set('capsule',`translate(${120*a} 0) scale(${1-.12*a} 1)`,1-smooth((u-.6)/.1));
                    set('fragments',`translate(${50*f} ${70*f}) rotate(${f*12} 430 620)`,smooth((u-.6)/.1));break;
                case 'activate':
                    set('moving',`translate(450 500) scale(${1-.12*a+recoil*.02}) translate(-450 -500)`);
                    set('reveal','',smooth((u-.35)/.35));break;
                case 'bypass': {
                    const p=a;set('moving',`translate(${600*p} ${-370*Math.sin(p*Math.PI)}) rotate(${-30*Math.cos(p*Math.PI)} ${200} ${665})`);
                    set('reveal','',smooth((u-.5)/.2));break;
                }
                case 'dock':
                    set('moving',`translate(${120*a-20*anticipation*(1-a)+recoil*3} 0)`);
                    for(let i=0;i<16;i++)set(`cell-${i}`,'',.25+.75*smooth((u-.5-(i%4)*.05-Math.floor(i/4)*.02)/.15));break;
            }
            let zoom=1, x=0, angle=0, sy=1;
            if(spec.camera==='push-in')zoom=1+.12*u;
            if(spec.camera==='pull-out')zoom=1.12-.12*u;
            if(spec.camera==='track-left')x=45-90*u;
            if(spec.camera==='track-right')x=-45+90*u;
            if(spec.camera==='overhead') {sy=.87;angle=-3+6*u}
            if(spec.camera==='oblique') {angle=-6+12*u;zoom=1.02}
            zoom=1+(zoom-1)*spec.strength*2;x*=spec.strength*2;angle*=spec.strength*2;
            camera.setAttribute('transform',`translate(${450+x} 500) rotate(${angle}) scale(${zoom} ${zoom*sy}) translate(-450 -500)`);
            // Lighting is resolved into SVG palette colors, avoiding compositor filter rounding.
            element.style.filter='none';
            shot.background.setAttribute('transform',`translate(${-x*.15} 0)`);
            shot.foreground.setAttribute('transform',`translate(${-x*.3} 0)`);
            const incoming=smooth(timeU/.09), outgoing=smooth((timeU-.92)/.08);
            const inner=scene.querySelector('.scene-inner');
            inner.style.opacity=spec.transition==='fade'?String(Math.min(incoming,1-outgoing)):'1';
            inner.style.transform=spec.transition==='slide'?`translateX(${40*(1-incoming)-40*outgoing}px)`:'none';
            let shutter=0;
            if(spec.transition==='closure')shutter=Math.max(1-incoming,outgoing);
            if(spec.transition==='object-wipe')shutter=Math.max(1-incoming,outgoing);
            shutters[0].setAttribute('transform',`translate(${-450*(1-shutter)} 0)`);
            shutters[1].setAttribute('transform',`translate(${450*(1-shutter)} 0)`);
            if(spec.transition==='object-wipe') {
                shutters[0].setAttribute('transform',`translate(${-900*(1-shutter)} 0)`);
                shutters[1].setAttribute('transform',`translate(${-900*(1-shutter)} 0)`);
            }
            if(spec.transition==='light-transfer')shot.background.setAttribute('opacity',String(.65+.35*Math.max(1-incoming,outgoing)));
            else shot.background.setAttribute('opacity','1');
            set('token',`translate(450 ${875-350*Math.max(1-incoming,outgoing)}) rotate(${90*Math.max(1-incoming,outgoing)})`,spec.continuityToken?1:0);
            if(spec.continuityToken==='defense-wedge') {
                if(spec.action==='balance') {
                    const handoff=smooth((timeU-.85)/.15);
                    const defense=part('defense')[0], svg=element.querySelector('svg');
                    // One world-to-screen mapping also places the shared transition object.
                    const anchor=new DOMPoint(735,550).matrixTransform(defense.getScreenCTM()).matrixTransform(svg.getScreenCTM().inverse());
                    set('token',`translate(${anchor.x*(1-handoff)+450*handoff} ${anchor.y*(1-handoff)+500*handoff}) scale(${1.4-.4*handoff})`,handoff);
                    defense.setAttribute('opacity',String(1-handoff));
                    part('token-shape')[0].setAttribute('points','-60,60 0,-60 60,60 0,60');
                } else if(spec.action==='block') {
                    const morph=smooth(timeU/.18);
                    const triangle=[[-60,60],[0,-60],[60,60],[0,60]], gate=[[-70,-180],[70,-180],[70,180],[-70,180]];
                    part('token-shape')[0].setAttribute('points',triangle.map((point,i)=>point.map((v,j)=>v*(1-morph)+gate[i][j]*morph).join(',')).join(' '));
                    set('token',`translate(${450+30*morph} ${500-95*morph})`,1-morph);
                }
            }
            scene.dataset.motionPhase=u<.25?'anticipation':u<.65?'action':u<.85?'follow-through':'hold';
        }
    };
}
