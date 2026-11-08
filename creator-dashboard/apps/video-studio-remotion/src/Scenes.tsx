import React from 'react';

/** Original vector scene library. Every scene is procedural SVG driven only by
 *  time/progress (deterministic, no assets, no randomness): safe to re-render. */
export type Pal={bg:string;ink:string;accent:string;sky:string;skyLow:string;far:string;mid:string;near:string;ground:string;light:string;warm:string};
type S={p:number;t:number;pal:Pal;index:number};

const clamp=(n:number,a=0,b=1)=>Math.min(b,Math.max(a,n));
const ease=(n:number)=>1-Math.pow(1-clamp(n),3);
const lerp=(a:number,b:number,k:number)=>a+(b-a)*k;
const rnd=(i:number)=>{const x=Math.sin(i*127.1+311.7)*43758.5453;return x-Math.floor(x);};
const parse=(h:string)=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
const luma=(h:string)=>{const [r,g,b]=parse(h);return (0.2126*r+0.7152*g+0.0722*b)/255;};
export const mix=(a:string,b:string,k:number)=>{const x=parse(a),y=parse(b);return '#'+x.map((v,i)=>Math.round(v+(y[i]-v)*k).toString(16).padStart(2,'0')).join('');};
/** Scenery always renders on its own mid-dark "stage" derived from the template accent,
 *  so illustrations stay punchy on both dark and light templates. */
export const palette=(bg:string,accent:string,ink:string):Pal=>{
  const stage=luma(bg)>.55?mix('#0c1530',accent,.34):mix(bg,accent,.04);
  return {bg:stage,ink,accent,
    sky:mix(stage,accent,.26),skyLow:mix(stage,mix(accent,'#ffb866',.55),.5),far:mix(stage,accent,.42),mid:mix(stage,accent,.26),
    near:mix(stage,'#000000',.4),ground:mix(stage,'#000000',.32),light:mix(accent,'#ffffff',.7),warm:mix(accent,'#ffd27a',.6)};
};

export const MOTIFS=['elephant','landmark','birds','map','sunrise','mountain','city','people','tech','nature','water','fire','book','idea','globe','money','heart','clock','shield','abstract'] as const;

const Cloud:React.FC<{x:number;y:number;s:number;c:string}>=({x,y,s,c})=><g transform={`translate(${x} ${y}) scale(${s})`} fill={c}>
  <ellipse cx="0" cy="0" rx="46" ry="20"/><ellipse cx="-28" cy="8" rx="30" ry="15"/><ellipse cx="30" cy="8" rx="34" ry="16"/><ellipse cx="8" cy="-14" rx="28" ry="18"/></g>;
const Clouds:React.FC<{t:number;pal:Pal;y?:number;o?:number}>=({t,pal,y=90,o=.16})=><g opacity={o}>
  {[0,1,2].map(i=><Cloud key={i} x={((t*(14+i*6)+i*320)%1000)-120} y={y+i*42+(i%2)*12} s={.8+i*.28} c={pal.light}/>)}</g>;
const Sun:React.FC<{x:number;y:number;r:number;t:number;pal:Pal;rays?:boolean}>=({x,y,r,t,pal,rays=true})=><g>
  <circle cx={x} cy={y} r={r*2.8} fill="url(#warm)"/>
  {rays && <g transform={`rotate(${t*8} ${x} ${y})`} stroke={pal.warm} strokeWidth="5" strokeLinecap="round" opacity=".5">
    {Array.from({length:14},(_,i)=>{const a=i/14*Math.PI*2,r1=r+16,r2=r1+(i%2?16:34);return <line key={i} x1={x+Math.cos(a)*r1} y1={y+Math.sin(a)*r1} x2={x+Math.cos(a)*r2} y2={y+Math.sin(a)*r2}/>;})}</g>}
  <circle cx={x} cy={y} r={r} fill={pal.warm}/></g>;
const Stars:React.FC<{t:number;pal:Pal;n?:number;h?:number}>=({t,pal,n=26,h=240})=><g fill={pal.light}>
  {Array.from({length:n},(_,i)=><circle key={i} cx={rnd(i+1)*800} cy={rnd(i+40)*h} r={1+rnd(i+7)*2} opacity={.25+.5*Math.abs(Math.sin(t*(.8+rnd(i)*1.5)+i))}/>)}</g>;

/* ---------- elephant herd on the savanna ---------- */
const Elephant:React.FC<{x:number;y:number;s:number;t:number;ph:number;fill:string;dark:string;tusk:string;eye:string}>=({x,y,s,t,ph,fill,dark,tusk,eye})=>{
  const sw=(k:number)=>Math.sin(t*4.2+ph+k*Math.PI)*15;
  const bob=Math.abs(Math.sin(t*4.2+ph))*-5;
  const leg=(lx:number,k:number,c:string)=><g transform={`rotate(${sw(k)} ${lx+13} 25)`}><rect x={lx} y="25" width="26" height="72" rx="11" fill={c}/><rect x={lx-1} y="88" width="28" height="12" rx="6" fill={dark}/></g>;
  return <g transform={`translate(${x} ${y+bob*s}) scale(${s})`}>
    {leg(30,1,dark)}{leg(132,0,dark)}
    <path d="M4 -18 q-22 26 -6 64" stroke={dark} strokeWidth="6" fill="none" strokeLinecap="round"/>
    <ellipse cx="105" cy="-10" rx="102" ry="64" fill={fill}/>
    {leg(70,0,fill)}{leg(172,1,fill)}
    <circle cx="224" cy="-28" r="46" fill={fill}/>
    <ellipse cx="196" cy="-22" rx="30" ry="46" fill={dark} opacity=".72" transform={`rotate(${Math.sin(t*2+ph)*5} 196 -50)`}/>
    <path d="M250 -8 C290 6 296 48 272 76" stroke={fill} strokeWidth="26" fill="none" strokeLinecap="round"/>
    <path d="M246 14 q24 16 38 6" stroke={tusk} strokeWidth="7" fill="none" strokeLinecap="round"/>
    <circle cx="238" cy="-40" r="4.5" fill={eye}/></g>;
};
const Elephants:React.FC<S>=({p,t,pal})=>{
  const dark=mix(pal.bg,pal.accent,.30);
  return <g>
    <Stars t={t} pal={pal} n={10} h={120}/>
    <Sun x={560} y={lerp(290,255,ease(p))} r={46} t={t} pal={pal}/>
    <Clouds t={t} pal={pal} y={70} o={.12}/>
    <path d="M0 330 C110 292 220 340 330 316 C450 290 560 338 800 308 V500 H0Z" fill={mix(pal.bg,pal.accent,.14)}/>
    <Elephant x={lerp(330,640,p)} y={320} s={.42} t={t} ph={2} fill={mix(pal.bg,pal.accent,.36)} dark={mix(pal.bg,pal.accent,.24)} tusk={pal.light} eye={pal.bg}/>
    <Elephant x={lerp(110,470,p)} y={352} s={.6} t={t} ph={1} fill={mix(pal.bg,pal.accent,.5)} dark={mix(pal.bg,pal.accent,.36)} tusk={pal.light} eye={pal.bg}/>
    <path d="M0 400 C150 372 300 414 450 388 C600 362 700 404 800 384 V500 H0Z" fill={pal.ground}/>
    <Elephant x={lerp(-90,420,p)} y={392} s={.86} t={t} ph={0} fill={mix(pal.bg,pal.accent,.66)} dark={dark} tusk={'#fff6dc'} eye={pal.bg}/>
    {Array.from({length:16},(_,i)=>{const k=((t*.55+rnd(i)*3)%1);return <circle key={i} cx={lerp(-90,420,p)+60+rnd(i+5)*230-k*40} cy={470-k*70} r={5+k*13} fill={pal.warm} opacity={.22*(1-k)}/>;})}
  </g>;
};

/* ---------- landmark with circling crowd ---------- */
const Landmark:React.FC<S>=({t,pal})=>{
  const dots=Array.from({length:18},(_,i)=>{const a=t*.45+i/18*Math.PI*2;return {x:400+Math.cos(a)*258,y:402+Math.sin(a)*54,z:Math.sin(a),i};});
  const dot=(d:{x:number;y:number;z:number;i:number})=><circle key={d.i} cx={d.x} cy={d.y} r={7+d.z*2.4} fill={d.i%3?pal.light:pal.warm} opacity={.5+d.z*.3}/>;
  return <g>
    <Stars t={t} pal={pal} n={34} h={200}/>
    <g transform={`rotate(${t*6} 400 230)`} opacity=".16" fill={pal.warm}>{Array.from({length:10},(_,i)=>{const a=i/10*Math.PI*2;return <polygon key={i} points={`400,230 ${400+Math.cos(a-.07)*520},${230+Math.sin(a-.07)*520} ${400+Math.cos(a+.07)*520},${230+Math.sin(a+.07)*520}`}/>;})}</g>
    <circle cx="400" cy="250" r="210" fill="url(#glow)"/>
    <ellipse cx="400" cy="405" rx="330" ry="78" fill={pal.ground}/>
    <ellipse cx="400" cy="405" rx="258" ry="54" fill="none" stroke={pal.accent} strokeOpacity=".25" strokeDasharray="4 12"/>
    {dots.filter(d=>d.z<0).map(dot)}
    <ellipse cx="410" cy="388" rx="120" ry="16" fill="#000" opacity=".4"/>
    <rect x="322" y="178" width="156" height="206" fill="#0d0d12" stroke={pal.accent} strokeWidth="3"/>
    <polygon points="322,178 346,160 500,160 478,178" fill="#1b1b24"/>
    <polygon points="478,178 500,160 500,366 478,384" fill="#08080b"/>
    <rect x="322" y="212" width="156" height="24" fill={pal.warm}/>
    {Array.from({length:9},(_,i)=><rect key={i} x={332+i*16.5} y="217" width="9" height="14" rx="2" fill="#0d0d12" opacity=".55"/>)}
    <rect x="380" y="298" width="40" height="86" rx="4" fill={pal.warm}/><rect x="387" y="306" width="26" height="78" rx="3" fill="#15110a"/>
    {dots.filter(d=>d.z>=0).map(dot)}
  </g>;
};

/* ---------- flock of birds ---------- */
const Bird:React.FC<{x:number;y:number;s:number;t:number;ph:number;c:string}>=({x,y,s,t,ph,c})=>{
  const f=Math.sin(t*9+ph);
  return <g transform={`translate(${x} ${y}) scale(${s})`} stroke={c} strokeWidth="7" strokeLinecap="round" fill="none">
    <path d={`M0 0 Q-24 ${-28*f} -52 ${-8*f+8}`}/><path d={`M0 0 Q24 ${-28*f} 52 ${-8*f+8}`}/>
    <ellipse cx="0" cy="3" rx="9" ry="5.5" fill={c} stroke="none"/></g>;
};
const Birds:React.FC<S>=({p,t,pal})=>{
  const lead=lerp(-40,640,p);
  return <g>
    <Sun x={150} y={140} r={40} t={t} pal={pal}/>
    <Clouds t={t} pal={pal} y={80} o={.2}/>
    {Array.from({length:9},(_,i)=>{const k=Math.ceil(i/2),side=i%2?1:-1;
      return <Bird key={i} x={lead-k*64} y={190+Math.sin(t*1.4)*12+(i?k*side*30:0)} s={.9-k*.04} t={t} ph={i*.7} c={mix(pal.bg,'#000000',.45)}/>;})}
    <path d="M0 410 C140 380 260 420 420 396 C560 376 680 420 800 394 V500 H0Z" fill={pal.ground}/>
    {Array.from({length:7},(_,i)=>{const k=((t*.3+i*.14)%1);return <circle key={i} cx={lead-60-i*46} cy={250+k*190} r="6" fill={pal.warm} opacity={.7*(1-k)}/>;})}
  </g>;
};

/* ---------- map with a drawn route ---------- */
const MapScene:React.FC<S>=({p,t,pal})=>{
  const pts=[[210,350],[330,318],[410,262],[520,246],[590,186]];
  const draw=ease(p*1.25);
  return <g>
    <rect x="110" y="56" width="580" height="388" rx="20" fill={mix(pal.bg,pal.warm,.14)} stroke={pal.accent} strokeOpacity=".4" transform="rotate(-1.5 400 250)"/>
    {Array.from({length:9},(_,i)=><path key={i} d={`M${130+i*65} 70V430M125 ${86+i*43}H675`} stroke={pal.accent} strokeOpacity=".12"/>)}
    <path d="M170 364 C186 262 260 214 340 222 C424 232 452 164 542 174 C626 184 652 256 604 336 C552 414 420 404 330 414 C250 424 160 424 170 364Z" fill={mix(pal.bg,pal.accent,.34)} stroke={pal.accent} strokeOpacity=".6" strokeWidth="2"/>
    <path d="M250 300 q40 -30 90 -6 M430 330 q50 -26 100 0" stroke={pal.accent} strokeOpacity=".3" fill="none" strokeWidth="2"/>
    <path d="M210 350 C270 330 330 318 410 262 S520 256 590 186" fill="none" stroke={pal.warm} strokeWidth="6" strokeLinecap="round" strokeDasharray="620" strokeDashoffset={620*(1-draw)}/>
    {pts.map(([x,y],i)=>{const on=ease(draw*5-i);return <g key={i} opacity={on} transform={`translate(${x} ${y-(1-on)*16})`}>
      <path d="M0 0 C-16 -22 -16 -42 0 -44 C16 -42 16 -22 0 0Z" fill={i===pts.length-1?pal.warm:pal.accent}/><circle cy="-30" r="5" fill={pal.bg}/></g>;})}
    <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r={14+(t*20%24)} fill="none" stroke={pal.warm} strokeOpacity={.5*(1-(t*20%24)/24)} strokeWidth="3"/>
    <g transform={`translate(620 112) rotate(${Math.sin(t)*6})`}><circle r="30" fill="none" stroke={pal.accent} strokeWidth="3"/><polygon points="0,-26 8,0 0,26 -8,0" fill={pal.warm}/><polygon points="0,-26 8,0 -8,0" fill={pal.light}/></g>
  </g>;
};

/* ---------- sunrise ---------- */
const Sunrise:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={30} h={200}/>
  <Sun x={400} y={lerp(430,238,ease(p))} r={74} t={t} pal={pal}/>
  <Clouds t={t} pal={pal} y={96} o={.22}/>
  <path d="M0 360 C120 320 220 380 360 346 C500 312 620 372 800 330 V500 H0Z" fill={pal.far}/>
  <path d="M0 410 C150 372 300 430 460 392 C600 360 700 416 800 388 V500 H0Z" fill={pal.mid}/>
  <path d="M0 450 C160 424 320 466 500 440 C640 420 720 456 800 440 V500 H0Z" fill={pal.ground}/>
  {[0,1,2,3].map(i=><Bird key={i} x={((t*60+i*140)%960)-80} y={150+i*26+Math.sin(t*2+i)*10} s={.5} t={t} ph={i} c={mix(pal.bg,'#000000',.4)}/>)}
</g>;

/* ---------- mountains ---------- */
const Mountain:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={20} h={150}/>
  <circle cx={600} cy={lerp(160,120,p)} r="44" fill={pal.light} opacity=".9"/>
  <Clouds t={t} pal={pal} y={80} o={.14}/>
  <g transform={`translate(${Math.sin(t*.25)*10-p*14} 0)`}>
    <path d="M-30 380 L120 238 L210 318 L330 196 L450 330 L580 226 L700 340 L830 250 V500 H-30Z" fill={pal.far}/>
    <polygon points="330,196 296,240 330,232 360,248" fill={pal.light} opacity=".7"/><polygon points="580,226 548,266 580,258 606,272" fill={pal.light} opacity=".7"/></g>
  <g transform={`translate(${Math.sin(t*.3)*16-p*30} 0)`}>
    <path d="M-40 430 L90 330 L190 400 L320 296 L440 410 L560 322 L690 418 L840 340 V500 H-40Z" fill={pal.mid}/></g>
  <g transform={`translate(${Math.sin(t*.35)*22-p*52} 0)`}>
    <path d="M-60 470 L60 410 L170 460 L300 396 L420 466 L560 408 L700 470 L860 420 V500 H-60Z" fill={pal.near}/></g>
</g>;

/* ---------- city skyline ---------- */
const City:React.FC<S>=({p,t,pal})=>{
  const b=Array.from({length:13},(_,i)=>({x:i*64-10,w:52+rnd(i)*20,h:90+rnd(i+9)*190}));
  return <g>
    <Stars t={t} pal={pal} n={34} h={180}/>
    <circle cx="640" cy="120" r="46" fill={pal.light} opacity=".85"/>
    {b.map((q,i)=>{const top=440-q.h*ease(p*1.4+.25);return <g key={i}>
      <rect x={q.x} y={top} width={q.w} height={500-top} fill={mix(pal.bg,pal.accent,.14+rnd(i+3)*.12)}/>
      {Array.from({length:Math.floor(q.h/34)},(_,r)=>Array.from({length:Math.floor(q.w/18)},(_,c)=>{const lit=Math.sin(t*(.6+rnd(i*7+r*3+c))+i*r+c)>-.15;
        return <rect key={r+'-'+c} x={q.x+7+c*16} y={top+10+r*30} width="9" height="14" rx="2" fill={lit?pal.warm:mix(pal.bg,pal.accent,.3)} opacity={lit?.85:.35}/>;}))}</g>;})}
    <rect x="0" y="446" width="800" height="54" fill={pal.ground}/>
    <rect x={((t*220)%1100)-200} y="468" width="120" height="6" rx="3" fill={pal.warm} opacity=".9"/>
    <rect x={800-((t*160)%1000)} y="482" width="90" height="5" rx="3" fill={pal.accent} opacity=".8"/>
  </g>;
};

/* ---------- people ---------- */
const People:React.FC<S>=({p,t,pal})=>{
  const xs=[170,285,400,515,630];
  return <g>
    <ellipse cx="400" cy="420" rx="330" ry="36" fill={pal.ground}/>
    <ellipse cx="400" cy="250" rx="260" ry="190" fill="url(#glow)"/>
    <path d={xs.map((x,i)=>(i?'L':'M')+x+' '+(184+(i%2)*10)).join(' ')} fill="none" stroke={pal.warm} strokeWidth="3" strokeDasharray="520" strokeDashoffset={520*(1-ease(p*1.3))} opacity=".6"/>
    {xs.map((x,i)=>{const on=ease(p*3-i*.25),bounce=Math.abs(Math.sin(t*3+i*1.1))*10,col=[pal.accent,pal.light,pal.warm,pal.light,pal.accent][i];
      return <g key={i} opacity={on} transform={`translate(${x} ${400-bounce+(1-on)*30})`}>
        <ellipse cx="0" cy={bounce-2} rx="34" ry="8" fill="#000" opacity=".3"/>
        <path d="M-34 0 v-52 a34 34 0 0 1 68 0 v52Z" fill={col} opacity=".9"/>
        <circle cx="0" cy="-112" r="27" fill={col}/>
        {i===2 && <path d={`M34 -40 q26 ${-30+Math.sin(t*6)*14} 30 -60`} stroke={col} strokeWidth="14" strokeLinecap="round" fill="none"/>}</g>;})}
  </g>;
};

/* ---------- tech ---------- */
const Tech:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={18} h={140}/>
  <ellipse cx="400" cy="250" rx="300" ry="190" fill="url(#glow)"/>
  <rect x="226" y="100" width="348" height="226" rx="16" fill={mix(pal.bg,'#000000',.45)} stroke={pal.accent} strokeWidth="4"/>
  {[0,1,2,3,4,5,6].map(i=>{const w=[150,210,100,240,170,120,200][i]*clamp(p*3.6-i*.38);return <rect key={i} x={254+(i%3===1?24:0)} y={128+i*28} width={Math.max(0,w)} height="12" rx="6" fill={i%3===0?pal.warm:i%3===1?pal.accent:pal.light} opacity=".85"/>;})}
  <rect x={254+((p*3.6)%1)*200} y="128" width="4" height="12" fill={pal.light} opacity={Math.sin(t*8)>0?.9:0}/>
  <path d="M190 340 H610 L584 366 H216Z" fill={mix(pal.bg,pal.accent,.35)} stroke={pal.accent} strokeWidth="3"/>
  {[0,1,2].map(i=><path key={i} d={`M${652-i*0}  ${150}`} fill="none"/>)}
  {[0,1,2].map(i=><path key={'w'+i} d={`M${640-(i+1)*18} 138 a${(i+1)*26} ${(i+1)*26} 0 0 1 ${(i+1)*36} 0`} fill="none" stroke={pal.warm} strokeWidth="5" strokeLinecap="round" opacity={.25+.6*Math.max(0,Math.sin(t*3-i*.9))}/>)}
  {[0,1,2,3,4,5].map(i=>{const a=t*.7+i/6*Math.PI*2;return <g key={i} transform={`translate(${400+Math.cos(a)*300} ${230+Math.sin(a)*150}) rotate(${t*30+i*20})`}>
    <polygon points="0,-20 17,-10 17,10 0,20 -17,10 -17,-10" fill={mix(pal.bg,pal.accent,.4)} stroke={i%2?pal.warm:pal.accent} strokeWidth="3"/><circle r="5" fill={pal.light}/></g>;})}
</g>;

/* ---------- nature / fields ---------- */
const Tree:React.FC<{x:number;y:number;s:number;t:number;ph:number;pal:Pal;c:string}>=({x,y,s,t,ph,pal,c})=><g transform={`translate(${x} ${y}) scale(${s})`}>
  <rect x="-9" y="-110" width="18" height="110" rx="6" fill={mix(pal.bg,'#5a3b1a',.6)}/>
  <g transform={`rotate(${Math.sin(t*1.1+ph)*3} 0 -90)`}><circle cx="0" cy="-150" r="58" fill={c}/><circle cx="-42" cy="-118" r="40" fill={mix(c,'#000000',.12)}/><circle cx="44" cy="-122" r="42" fill={mix(c,pal.light,.08)}/></g></g>;
const Nature:React.FC<S>=({p,t,pal})=><g>
  <Sun x={620} y={124} r={38} t={t} pal={pal}/><Clouds t={t} pal={pal} y={70} o={.16}/>
  <path d="M0 380 C160 350 300 396 460 368 C600 344 700 384 800 360 V500 H0Z" fill={mix(pal.bg,'#3f8f4e',.35)}/>
  <Tree x={150} y={400} s={.9*ease(p*3)+.1} t={t} ph={0} pal={pal} c={mix(pal.bg,'#3fa65b',.6)}/>
  <Tree x={520} y={392} s={.75*ease(p*3-.3)+.1} t={t} ph={2} pal={pal} c={mix(pal.bg,'#58b86a',.55)}/>
  <Tree x={690} y={404} s={.6*ease(p*3-.6)+.1} t={t} ph={4} pal={pal} c={mix(pal.bg,'#3fa65b',.5)}/>
  <path d="M0 410 C150 388 300 430 480 406 C640 386 720 424 800 406 V500 H0Z" fill={mix(pal.bg,'#2f7a3f',.45)}/>
  {Array.from({length:46},(_,i)=>{const x=i*18+rnd(i)*10,h=22+rnd(i+4)*26,sway=Math.sin(t*2+i*.7)*7;return <path key={i} d={`M${x} 470 q${sway} ${-h/2} ${sway*1.6} ${-h}`} stroke={mix(pal.bg,'#58b86a',.7)} strokeWidth="4" strokeLinecap="round" fill="none" opacity=".85"/>;})}
  {Array.from({length:9},(_,i)=>{const k=((t*.16+rnd(i)*2)%1);return <ellipse key={i} cx={rnd(i+2)*800+Math.sin(t+i)*30} cy={k*470} rx="9" ry="4.5" fill={mix(pal.bg,'#9bd06a',.6)} opacity=".8" transform={`rotate(${t*90+i*40} ${rnd(i+2)*800} ${k*470})`}/>;})}
</g>;

/* ---------- water ---------- */
const wavePath=(t:number,base:number,amp:number,period:number,speed:number)=>{
  let d=`M0 ${base+Math.sin((0+t*speed)/period)*amp}`;
  for(let x=20;x<=800;x+=20)d+=` L${x} ${base+Math.sin((x+t*speed)/period)*amp}`;
  return d+' V500 H0Z';
};
const Water:React.FC<S>=({p,t,pal})=><g>
  <Sun x={560} y={lerp(300,230,ease(p))} r={46} t={t} pal={pal}/><Clouds t={t} pal={pal} y={70} o={.16}/>
  <path d={wavePath(t,330,10,38,120)} fill={mix(pal.bg,'#2a7fb5',.45)}/>
  <g transform={`translate(${lerp(120,420,p)} ${326+Math.sin(t*2)*6}) rotate(${Math.sin(t*2)*5})`}>
    <path d="M-70 0 H70 L50 34 H-50Z" fill={mix(pal.bg,'#7a4a1f',.55)}/><rect x="-3" y="-120" width="6" height="120" fill={pal.light}/>
    <path d="M6 -116 L72 -20 H6Z" fill={pal.light}/><path d="M-6 -100 L-52 -20 H-6Z" fill={pal.warm}/></g>
  <path d={wavePath(t,368,14,46,180)} fill={mix(pal.bg,'#1f6fa3',.55)}/>
  <path d={wavePath(t,414,16,54,-150)} fill={mix(pal.bg,'#16578a',.6)}/>
  <path d={wavePath(t,456,12,40,90)} fill={mix(pal.bg,'#0f4271',.65)}/>
  {Array.from({length:12},(_,i)=>{const k=((t*.5+rnd(i)*3)%1);return <circle key={i} cx={rnd(i+8)*800} cy={500-k*160} r={3+rnd(i)*5} fill={pal.light} opacity={.3*(1-k)}/>;})}
</g>;

/* ---------- fire ---------- */
const Flame:React.FC<{x:number;y:number;s:number;t:number;ph:number;c:string}>=({x,y,s,t,ph,c})=>
  <path d="M0 0 C-44 -22 -56 -96 0 -178 C56 -96 44 -22 0 0Z" fill={c} transform={`translate(${x} ${y}) scale(${s*(1+Math.sin(t*9+ph)*.07)} ${s*(1+Math.sin(t*7+ph*1.7)*.1)}) skewX(${Math.sin(t*5+ph)*4})`}/>;
const Fire:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={26} h={220}/>
  <ellipse cx="400" cy="300" rx="260" ry="220" fill="url(#warm)"/>
  <rect x="270" y="410" width="260" height="30" rx="14" fill="#2b1a0e" transform="rotate(-6 400 425)"/><rect x="270" y="412" width="260" height="30" rx="14" fill="#3a2412" transform="rotate(7 400 425)"/>
  <Flame x={340} y={420} s={.78*ease(p*4)+.2} t={t} ph={1} c={mix(pal.accent,'#ff5a1f',.65)}/>
  <Flame x={460} y={420} s={.82*ease(p*4)+.2} t={t} ph={3} c={mix(pal.accent,'#ff5a1f',.65)}/>
  <Flame x={400} y={424} s={1.05*ease(p*4)+.2} t={t} ph={0} c={mix(pal.accent,'#ff9b2e',.7)}/>
  <Flame x={400} y={426} s={.62*ease(p*4)+.15} t={t} ph={2} c={'#fff2b0'}/>
  {Array.from({length:22},(_,i)=>{const k=((t*.5+rnd(i)*2)%1);return <circle key={i} cx={400+Math.sin(t*3+i)*70+(rnd(i+3)-.5)*160*k} cy={410-k*330} r={2+rnd(i+6)*4*(1-k)} fill={pal.warm} opacity={.9*(1-k)}/>;})}
</g>;

/* ---------- book ---------- */
const Book:React.FC<S>=({p,t,pal})=>{
  const flip=(t*.55)%1,cx=Math.cos(flip*Math.PI);
  const lines=(x0:number,dir:number)=>Array.from({length:9},(_,i)=><path key={i} d={`M${x0} ${170+i*22}h${dir*(i%4===3?110:160)}`} stroke={pal.ink} strokeOpacity=".55" strokeWidth="5" strokeLinecap="round" strokeDasharray="180" strokeDashoffset={180*(1-clamp(p*3-i*.18))}/>);
  return <g>
    <ellipse cx="400" cy="250" rx="290" ry="200" fill="url(#glow)"/>
    <ellipse cx="400" cy="420" rx="300" ry="34" fill="#000" opacity=".35"/>
    <path d="M400 128 Q300 104 188 136 V392 Q300 362 400 392Z" fill={mix(pal.light,pal.bg,.18)} stroke={pal.accent} strokeWidth="3"/>
    <path d="M400 128 Q500 104 612 136 V392 Q500 362 400 392Z" fill={mix(pal.light,pal.bg,.1)} stroke={pal.accent} strokeWidth="3"/>
    <path d="M176 142 V402 Q300 372 400 402 Q500 372 624 402 V142" fill="none" stroke={mix(pal.accent,'#000',.3)} strokeWidth="9" strokeLinecap="round"/>
    {lines(222,1)}{lines(578,-1)}
    <g transform={`translate(400 0) scale(${cx} 1) translate(-400 0)`} opacity={.92}>
      <path d="M400 128 Q500 104 612 136 V392 Q500 362 400 392Z" fill={mix(pal.light,pal.bg,.05)} stroke={pal.accent} strokeWidth="2"/></g>
    {Array.from({length:14},(_,i)=>{const k=((t*.35+rnd(i)*2)%1);return <text key={i} x={190+rnd(i)*420} y={150-k*130} fontSize={20+rnd(i+3)*16} fill={i%2?pal.warm:pal.light} opacity={.8*(1-k)} fontWeight="700">{'ا'}</text>;})}
  </g>;
};

/* ---------- idea ---------- */
const Idea:React.FC<S>=({p,t,pal})=>{
  const on=ease(p*3),pulse=1+Math.sin(t*4)*.05;
  return <g>
    <Stars t={t} pal={pal} n={24} h={210}/>
    <circle cx="400" cy="210" r={260*on} fill="url(#warm)"/>
    <g transform={`rotate(${t*10} 400 210)`} stroke={pal.warm} strokeWidth="6" strokeLinecap="round" opacity={.7*on}>
      {Array.from({length:12},(_,i)=>{const a=i/12*Math.PI*2,r1=136,r2=136+(i%2?22:44)*pulse;return <line key={i} x1={400+Math.cos(a)*r1} y1={210+Math.sin(a)*r1} x2={400+Math.cos(a)*r2} y2={210+Math.sin(a)*r2}/>;})}</g>
    <circle cx="400" cy="210" r="98" fill={mix(pal.bg,pal.warm,.35+.4*on)} stroke={pal.warm} strokeWidth="5"/>
    <path d="M360 330 C352 296 328 270 328 226 a72 72 0 0 1 144 0 C472 270 448 296 440 330Z" fill={mix(pal.bg,pal.warm,.2+.6*on)} opacity=".0"/>
    <path d="M368 214 q16 -26 32 0 t32 0" stroke={pal.light} strokeWidth="6" fill="none" strokeLinecap="round" opacity={.4+.6*on}/>
    <path d="M400 214 V300" stroke={pal.light} strokeWidth="5" opacity=".6"/>
    <rect x="364" y="304" width="72" height="22" rx="8" fill={mix(pal.bg,pal.accent,.5)}/><rect x="372" y="328" width="56" height="18" rx="8" fill={mix(pal.bg,pal.accent,.4)}/><rect x="384" y="348" width="32" height="14" rx="6" fill={pal.accent}/>
    {Array.from({length:8},(_,i)=>{const a=t*.9+i/8*Math.PI*2;return <circle key={i} cx={400+Math.cos(a)*190} cy={210+Math.sin(a)*120} r={4+i%3*2} fill={i%2?pal.warm:pal.light} opacity=".85"/>;})}
  </g>;
};

/* ---------- globe ---------- */
const Globe:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={30} h={500}/>
  <circle cx="400" cy="250" r="230" fill="url(#glow)"/>
  <circle cx="400" cy="250" r="150" fill={mix(pal.bg,pal.accent,.3)} stroke={pal.accent} strokeWidth="4"/>
  {[0,1,2,3].map(k=><ellipse key={k} cx="400" cy="250" rx={Math.abs(Math.cos(t*.8+k*Math.PI/4))*150} ry="150" fill="none" stroke={pal.light} strokeOpacity=".5" strokeWidth="2"/>)}
  {[-90,-45,0,45,90].map(dy=><ellipse key={dy} cx="400" cy={250+dy} rx={Math.sqrt(Math.max(0,150*150-dy*dy))} ry={10+Math.abs(dy)/10} fill="none" stroke={pal.light} strokeOpacity=".35" strokeWidth="2"/>)}
  {[0,1,2].map(i=>{const a=t*.8+i*2.1,x=400+Math.sin(a)*120,z=Math.cos(a);return z>0?<circle key={i} cx={x} cy={250-60+i*60} r="9" fill={pal.warm}/>:null;})}
  <g transform="rotate(-24 400 250)"><ellipse cx="400" cy="250" rx="230" ry="62" fill="none" stroke={pal.accent} strokeOpacity=".6" strokeWidth="3" strokeDasharray="3 10"/>
    <circle cx={400+Math.cos(t*1.1)*230} cy={250+Math.sin(t*1.1)*62} r="12" fill={pal.warm}/></g>
</g>;

/* ---------- money ---------- */
const Money:React.FC<S>=({p,t,pal})=>{
  const coin=(x:number,y:number,k:number)=><g key={x+'-'+y} transform={`translate(${x} ${y})`}><rect x="-38" y="0" width="76" height="12" fill={mix(pal.warm,'#000000',.25)}/><ellipse cx="0" cy="12" rx="38" ry="12" fill={mix(pal.warm,'#000000',.25)}/><ellipse cx="0" cy="0" rx="38" ry="12" fill={pal.warm}/><ellipse cx="0" cy="0" rx="24" ry="7" fill="none" stroke={mix(pal.warm,'#000000',.2)} strokeWidth="2" opacity={k}/></g>;
  return <g>
    <ellipse cx="400" cy="440" rx="320" ry="40" fill={pal.ground}/>
    {[0,1,2,3,4].map(i=>{const n=Math.round((i+2)*1.5*ease(p*1.6-i*.1));return <g key={i}>{Array.from({length:n},(_,k)=>coin(150+i*125,420-k*17,1))}</g>;})}
    <path d="M120 270 L260 230 L360 250 L520 150 L640 120" fill="none" stroke={pal.accent} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="640" strokeDashoffset={640*(1-ease(p*1.3))}/>
    <polygon points="640,96 676,134 626,142" fill={pal.accent} opacity={ease(p*2-.8)}/>
    {Array.from({length:10},(_,i)=>{const k=((t*.4+rnd(i)*2)%1);return <circle key={i} cx={120+rnd(i)*560} cy={380-k*300} r={5+rnd(i+3)*5} fill={pal.warm} opacity={.8*(1-k)}/>;})}
  </g>;
};

/* ---------- heart ---------- */
const Heart:React.FC<S>=({p,t,pal})=>{
  const beat=Math.pow(Math.max(0,Math.sin(t*5.5)),6),sc=1+beat*.13;
  const off=(t*220)%520;
  return <g>
    <circle cx="400" cy="230" r="230" fill="url(#glow)"/>
    {[0,1,2].map(i=>{const k=((t*.9+i*.33)%1);return <circle key={i} cx="400" cy="230" r={120+k*160} fill="none" stroke={pal.accent} strokeOpacity={.4*(1-k)} strokeWidth="4"/>;})}
    <g transform={`translate(400 240) scale(${sc*(.5+.5*ease(p*3))}) translate(-400 -270)`}>
      <path d="M400 390 C250 300 230 180 320 150 C370 135 400 165 400 185 C400 165 430 135 480 150 C570 180 550 300 400 390Z" fill={mix(pal.accent,'#ff3b5c',.7)} stroke={pal.light} strokeWidth="4" strokeOpacity=".5"/>
      <path d="M330 190 q22 -22 44 -4" stroke="#fff" strokeOpacity=".5" strokeWidth="8" strokeLinecap="round" fill="none"/></g>
    <path d={`M80 440 H220 l22 -40 l30 80 l26 -110 l24 70 l16 -22 H720`} fill="none" stroke={pal.warm} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="260 700" strokeDashoffset={-off+260}/>
  </g>;
};

/* ---------- clock ---------- */
const Clock:React.FC<S>=({p,t,pal})=><g>
  <circle cx="400" cy="250" r="240" fill="url(#glow)"/>
  <circle cx="400" cy="250" r="160" fill={mix(pal.bg,'#000000',.3)} stroke={pal.accent} strokeWidth="6"/>
  {Array.from({length:60},(_,i)=>{const a=i/60*Math.PI*2-Math.PI/2,r1=i%5?146:132;return <line key={i} x1={400+Math.cos(a)*r1} y1={250+Math.sin(a)*r1} x2={400+Math.cos(a)*152} y2={250+Math.sin(a)*152} stroke={i%5?pal.accent:pal.light} strokeWidth={i%5?2:5} strokeLinecap="round" opacity={i%5?.5:1}/>;})}
  <g transform={`rotate(${p*60+t*4} 400 250)`}><rect x="394" y="168" width="12" height="90" rx="6" fill={pal.light}/></g>
  <g transform={`rotate(${p*720+t*30} 400 250)`}><rect x="396" y="124" width="8" height="136" rx="4" fill={pal.warm}/></g>
  <circle cx="400" cy="250" r="12" fill={pal.warm}/>
  {Array.from({length:6},(_,i)=>{const a=t*.6+i/6*Math.PI*2;return <circle key={i} cx={400+Math.cos(a)*205} cy={250+Math.sin(a)*205} r="6" fill={i%2?pal.warm:pal.light} opacity=".8"/>;})}
</g>;

/* ---------- shield ---------- */
const Shield:React.FC<S>=({p,t,pal})=>{
  const draw=ease(p*2);
  return <g>
    <circle cx="400" cy="250" r="240" fill="url(#glow)"/>
    {[0,1,2].map(i=>{const k=((t*.7+i*.33)%1);return <circle key={i} cx="400" cy="250" r={150+k*160} fill="none" stroke={pal.accent} strokeOpacity={.45*(1-k)} strokeWidth="4"/>;})}
    <path d="M400 62 L598 138 V266 Q598 388 400 450 Q202 388 202 266 V138Z" fill={mix(pal.bg,pal.accent,.3)} stroke={pal.accent} strokeWidth="8" strokeDasharray="1100" strokeDashoffset={1100*(1-draw)} strokeLinejoin="round"/>
    <path d="M400 104 L558 164 V264 Q558 360 400 410 Q242 360 242 264 V164Z" fill="none" stroke={pal.light} strokeOpacity=".4" strokeWidth="3"/>
    <path d="M326 258 L384 316 L482 196" fill="none" stroke={pal.light} strokeWidth="26" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="300" strokeDashoffset={300*(1-ease(p*2.4-.6))}/>
  </g>;
};

/* ---------- abstract fallback (never pretends to be a data chart) ---------- */
const Abstract:React.FC<S>=({p,t,pal})=><g>
  <Stars t={t} pal={pal} n={26} h={500}/>
  <circle cx="400" cy="250" r="250" fill="url(#glow)"/>
  {[0,1,2].map(k=><ellipse key={k} cx="400" cy="250" rx={240-k*40} ry={82+k*30} fill="none" stroke={k%2?pal.warm:pal.accent} strokeOpacity=".55" strokeWidth="3" transform={`rotate(${t*(12+k*8)+k*60} 400 250)`}/>)}
  {[0,1,2,3,4,5].map(i=>{const a=t*(.6+i*.09)+i,r=70+i*28;return <circle key={i} cx={400+Math.cos(a)*r*1.5} cy={250+Math.sin(a)*r*.62} r={8+i%3*4} fill={i%2?pal.light:pal.warm} opacity=".9"/>;})}
  <circle cx="400" cy="250" r={46+Math.sin(t*2)*4+p*10} fill={pal.accent}/><circle cx="400" cy="250" r="22" fill={pal.light}/>
</g>;

const SCENES:Record<string,React.FC<S>>={elephant:Elephants,landmark:Landmark,birds:Birds,map:MapScene,sunrise:Sunrise,mountain:Mountain,city:City,people:People,tech:Tech,
  nature:Nature,water:Water,fire:Fire,book:Book,idea:Idea,globe:Globe,money:Money,heart:Heart,clock:Clock,shield:Shield,abstract:Abstract};

export const MotifScene:React.FC<{motif:string;progress:number;time:number;accent:string;bg:string;ink:string;index:number}>=({motif,progress,time,accent,bg,ink,index})=>{
  const pal=palette(bg,accent,ink);
  const Scene=SCENES[motif]||Abstract;
  const enter=ease(progress/.12);
  return <svg viewBox="0 0 800 500" width="100%" height="100%" role="img" aria-label={'Ilustrasi '+motif}>
    <defs>
      <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={pal.sky}/><stop offset="1" stopColor={pal.skyLow}/></linearGradient>
      <radialGradient id="glow"><stop offset="0" stopColor={accent} stopOpacity=".5"/><stop offset="1" stopColor={accent} stopOpacity="0"/></radialGradient>
      <radialGradient id="warm"><stop offset="0" stopColor={pal.warm} stopOpacity=".6"/><stop offset="1" stopColor={pal.warm} stopOpacity="0"/></radialGradient>
      <radialGradient id="vig" cx=".5" cy=".5" r=".8"><stop offset=".6" stopColor="#000" stopOpacity="0"/><stop offset="1" stopColor="#000" stopOpacity=".22"/></radialGradient>
      <clipPath id="card"><rect width="800" height="500" rx="38"/></clipPath>
    </defs>
    <g clipPath="url(#card)" opacity={enter}>
      <rect width="800" height="500" fill="url(#sky)"/>
      <g transform={`translate(400 250) scale(${1+progress*.05}) translate(-400 -250)`}><Scene p={progress} t={time} pal={pal} index={index}/></g>
      <rect width="800" height="500" fill="url(#vig)"/>
    </g>
    <rect x="1.5" y="1.5" width="797" height="497" rx="37" fill="none" stroke={accent} strokeOpacity=".5" strokeWidth="3"/>
  </svg>;
};

/** Layered ambient motion behind every shot (particles + soft blobs). */
export const Backdrop:React.FC<{effect:string;accent:string;t:number;width:number;height:number;unit:number}>=({effect,accent,t,width,height,unit})=>{
  const n=effect==='minimal'?9:effect==='kinetic'||effect==='urgent'?30:20;
  const speed=effect==='kinetic'?.1:effect==='urgent'?.07:.028;
  return <div style={{position:'absolute',inset:0,overflow:'hidden',pointerEvents:'none'}}>
    {[0,1].map(i=><div key={i} style={{position:'absolute',left:(i?58:-12)+Math.sin(t*.3+i*2)*5+'%',top:(i?52:6)+Math.cos(t*.25+i)*4+'%',width:width*.7,height:width*.7,borderRadius:'50%',
      background:`radial-gradient(circle,${accent}${i?'22':'30'},transparent 66%)`}}/>)}
    {Array.from({length:n},(_,i)=>{const k=1-((t*speed*(.6+rnd(i))+rnd(i+11))%1);
      const size=(effect==='calm'?6+rnd(i+4)*16:3+rnd(i+4)*7)*unit;
      return <div key={i} style={{position:'absolute',left:rnd(i+50)*width+Math.sin(t*.6+i)*26*unit,top:k*height,width:size,height:size,borderRadius:'50%',
        background:accent,opacity:(.07+.2*rnd(i+8))*Math.sin(k*Math.PI)}}/>;})}
  </div>;
};
