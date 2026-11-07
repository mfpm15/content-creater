import React from 'react';
import {literalNumbers} from './timeline.mjs';
import type {Shot} from './types';

/** A small, honest visual vocabulary: no invented footage or external assets. */
type Kind = 'calendar'|'medical'|'facilities'|'warning'|'security'|'verified'|'device'|'people'|'data'|'story';
export function treatmentFor(shot: Pick<Shot,'title'|'subject'|'family'>): Kind {
  const s=(shot.title+' '+shot.subject).toLowerCase();
  if (/(darah|blood|donor|transfusi|rumah sakit)/i.test(s)) return 'medical';
  if (/(fasilitas|lokasi|gedung|cabang|facility|facilities|data center)/i.test(s)) return 'facilities';
  if (/(ganggu|terhenti|outage|down|gagal|risiko|bahaya|ancaman|warning|krisis)/i.test(s)) return 'warning';
  if (/(siber|cyber|security|keamanan|peretas|enkripsi|firewall|serangan)/i.test(s)) return 'security';
  if (/(resmi|verifikasi|cek fakta|sumber|verified|klarifikasi|informasi)/i.test(s)) return 'verified';
  if (/(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|tanggal|kronologi|timeline)/i.test(s)) return 'calendar';
  if (/(aplikasi|ponsel|telepon|laptop|dashboard|perangkat|device|layar)/i.test(s)) return 'device';
  if (/(manusia|orang|pasien|pegawai|pengguna|pelanggan|masyarakat|people|tim)/i.test(s)) return 'people';
  if (shot.family==='data' || literalNumbers(shot.title).length>0) return 'data';
  return 'story';
}
const clamp=(n:number)=>Math.min(1,Math.max(0,n));
const smooth=(n:number)=>1-Math.pow(1-clamp(n),3);
const enter=(p:number,delay=0)=>smooth((p-delay)/.3);
type Props={shot:Shot;progress:number;accent:string;index:number};

export const Illustration: React.FC<Props> = ({shot,progress:p,accent,index}) => {
  const kind=treatmentFor(shot);
  const ink=kind==='warning'?'#fc7375':accent;
  const drift=Math.sin(p*Math.PI*3+index)*7;
  const numbers=literalNumbers(shot.title+' '+shot.subject).slice(0,3);
  const move=(delay=0)=>'translate(0 '+((1-enter(p,delay))*36+drift)+')';
  return <svg viewBox="0 0 800 500" width="100%" height="100%" role="img" aria-label={'Visual '+kind}>
    <defs>
      <radialGradient id="vignette"><stop offset="0%" stopColor={ink} stopOpacity=".3"/><stop offset="100%" stopColor={ink} stopOpacity="0"/></radialGradient>
      <linearGradient id="surface" x1="0" x2="1" y1="0" y2="1">
        <stop offset="0" stopColor="#15394d"/><stop offset="1" stopColor="#06111f"/>
      </linearGradient>
    </defs>
    <ellipse cx="400" cy="270" rx="355" ry="225" fill="url(#vignette)"/>
    <g fill="none" stroke={ink} strokeWidth="1" opacity=".17">
      <path d="M75 90H725M75 408H725M110 60V440M690 60V440"/>
      <circle cx="400" cy="250" r="202" strokeDasharray="2 14"/>
    </g>
    {shot.diagram ? <>
      {shot.diagram.kind==='process' && <path d="M400 70V440" fill="none" stroke={ink} strokeWidth="5"
        strokeDasharray="370" strokeDashoffset={370*(1-p)} opacity=".75"/>}
      {shot.diagram.labels.map((label,i)=>{
        const process=shot.diagram?.kind==='process';
        const count=shot.diagram!.labels.length, cx=process?400:210+i*380;
        const cy=process?75+i*340/(count-1):240, w=process?660:340;
        return <g key={i} opacity={enter(p,i*.11)} transform={move(i*.11)}>
          <rect x={cx-w/2+5} y={cy-(process?35:116)+9} width={w} height={process?70:232} rx="18" fill="#020c17" opacity=".6"/>
          <rect x={cx-w/2} y={cy-(process?35:116)} width={w} height={process?70:232} rx="18"
            fill="url(#surface)" stroke={ink} strokeWidth="2.5"/>
          <text x={cx} y={cy+9} fill="#f5fcff" textAnchor="middle" fontWeight="700" fontSize={process?27:30}
            textLength={label.length>28?w-35:undefined} lengthAdjust="spacingAndGlyphs">{label}</text>
        </g>;
      })}
    </> : kind==='calendar' ? <g opacity={enter(p)} transform={move()}>
      <rect x="251" y="70" width="298" height="350" rx="34" fill="url(#surface)" stroke={ink} strokeWidth="4"/>
      <path d="M251 162H549" stroke={ink} strokeWidth="5"/>
      <path d="M325 56V108M475 56V108" stroke="#f4fbff" strokeWidth="16" strokeLinecap="round"/>
      <text x="400" y="312" fontSize="140" fontWeight="900" fill="#f4fbff" textAnchor="middle">
        {numbers[0]||'01'}
      </text>
      <text x="400" y="365" textAnchor="middle" fontSize="23" letterSpacing="5" fill={ink}>KRONOLOGI</text>
    </g> : kind==='medical' ? <g opacity={enter(p)} transform={move()}>
      <path d="M400 60V115" stroke="#e0f5ff" strokeWidth="13" strokeLinecap="round"/>
      <rect x="293" y="109" width="214" height="285" rx="35" fill="url(#surface)" stroke={ink} strokeWidth="4"/>
      <rect x="338" y="83" width="125" height="35" rx="9" fill="#e0f5ff"/>
      <path d="M400 152C374 194 354 231 354 260A46 46 0 00446 260C446 231 426 194 400 152Z" fill="#ff627e"/>
      <path d="M346 333H454M400 307V358" stroke="#d7f3ff" strokeWidth="10" strokeLinecap="round"/>
      <path d="M508 234C583 234 566 352 633 352" fill="none" stroke={ink} strokeWidth="5"
        strokeDasharray="12 17" strokeDashoffset={-p*140}/>
      <circle cx="633" cy="352" r="14" fill={ink}/>
    </g> : kind==='facilities' ? <>
      <path d="M145 371H652" fill="none" stroke={ink} strokeWidth="4" strokeDasharray="15 15" strokeDashoffset={-p*80}/>
      {[0,1,2].map(n=>{
        const x=105+n*221, y=n===1?135:180;
        return <g key={n} opacity={enter(p,n*.13)} transform={move(n*.13)}>
          <rect x={x} y={y} width="157" height="202" rx="16" fill="url(#surface)" stroke={ink} strokeWidth="3"/>
          <rect x={x+53} y={y-28} width="52" height="35" rx="5" fill={ink}/>
          <path d={'M'+(x+79)+' '+(y-24)+'v26m-13-13h26'} stroke="#082033" strokeWidth="7"/>
          {[0,1,2].map(q=><rect key={q} x={x+20+q*45} y={y+69} width="29" height="48" rx="4" fill={ink} opacity=".35"/>)}
          <rect x={x+59} y={y+152} width="40" height="50" rx="4" fill={ink} opacity=".45"/>
          <text x={x+78} y={y+39} fill="#edfaff" fontSize="23" fontWeight="900" textAnchor="middle">{String(n+1).padStart(2,'0')}</text>
        </g>;
      })}
    </> : kind==='warning' ? <g opacity={enter(p)} transform={move()}>
      <circle cx="400" cy="258" r={178+p*14} fill="none" stroke={ink} strokeWidth="4"
        strokeDasharray="16 12" strokeDashoffset={-p*90} opacity=".6"/>
      <path d="M400 79L612 417H188Z" stroke={ink} strokeWidth="7" fill="#2a1727"/>
      <path d="M400 188V292" stroke="#fff4e8" strokeWidth="26" strokeLinecap="round"/>
      <circle cx="400" cy="348" r="16" fill="#fff4e8"/>
      {[0,1,2].map(i=><rect key={i} x={110+i*212} y={85+i*22} width="90" height="8"
        transform={'rotate(-11 '+(110+i*212)+' '+(85+i*22)+')'} fill={ink} opacity={.22+.16*Math.sin(p*13+i)}/>)}
    </g> : kind==='security' ? <g opacity={enter(p)} transform={move()}>
      <circle cx="400" cy="255" r="186" stroke={ink} strokeDasharray="7 18" strokeDashoffset={p*70}
        strokeWidth="4" opacity=".5" fill="none"/>
      <path d="M400 70L590 143V263Q590 372 400 438Q210 372 210 263V143Z" fill="url(#surface)" stroke={ink} strokeWidth="6"/>
      <path d="M400 106L546 164V261Q546 338 400 390Q254 338 254 261V164Z" fill="none" stroke={ink} strokeWidth="2" opacity=".45"/>
      <rect x="328" y="237" width="144" height="109" rx="15" fill={ink}/>
      <path d="M354 232V205A46 46 0 01446 205V232" stroke="#f0fbff" fill="none" strokeWidth="17" strokeLinecap="round"/>
      <circle cx="400" cy="281" r="15" fill="#082034"/>
      <path d="M400 284V316" stroke="#082034" strokeWidth="12" strokeLinecap="round"/>
    </g> : kind==='verified' ? <g opacity={enter(p)} transform={move()}>
      <rect x="243" y="71" width="290" height="341" rx="22" fill="#102337" stroke={ink} strokeWidth="3" transform="rotate(-7 400 240)"/>
      <rect x="278" y="101" width="285" height="336" rx="22" fill="url(#surface)" stroke={ink} strokeWidth="3"/>
      {[0,1,2,3].map(i=><rect key={i} x="319" y={170+i*50} width={183-i*18} height="11" rx="5"
        fill="#cae5f3" opacity={.28+.13*i}/>)}
      <circle cx="523" cy="354" r="70" fill={ink}/>
      <path d="M482 351L511 378L561 316" fill="none" stroke="#051723" strokeWidth="18" strokeLinecap="round"
        strokeDasharray="125" strokeDashoffset={125*(1-p)}/>
    </g> : kind==='data' ? (numbers.length?numbers:['—']).map((n,i,all)=>{
      const x=400+(i-(all.length-1)/2)*225;
      return <g key={i} opacity={enter(p,i*.12)} transform={'translate('+x+' '+(250+36*(1-enter(p,i*.12)))+')'}>
        <circle r="101" fill="url(#surface)" stroke={ink} strokeWidth="3"/>
        <circle r="117" fill="none" stroke={ink} strokeDasharray="140 600" strokeDashoffset={-p*160} strokeWidth="7" opacity=".65"/>
        <text textAnchor="middle" dy=".35em" fontSize={Math.min(52,255/n.length)} fontWeight="800" fill="#f4fbff">{n}</text>
      </g>;
    }) : kind==='device' ? <g opacity={enter(p)} transform={move()}>
      <rect x="260" y="68" width="280" height="350" rx="34" fill="url(#surface)" stroke={ink} strokeWidth="4"/>
      <rect x="281" y="99" width="238" height="281" rx="13" fill="#071727" stroke={ink} strokeWidth="1.5"/>
      {[0,1,2].map(i=><rect key={i} x="306" y={151+i*65} width={180-i*20} height={17+i*2} rx="8" fill={ink} opacity={.57-i*.12}/>)}
      <circle cx="400" cy="401" r="8" fill={ink}/>
    </g> : kind==='people' ? [0,1,2].map(i=>{
      const x=220+i*182;
      return <g key={i} opacity={enter(p,i*.14)} transform={move(i*.14)}>
        <circle cx={x} cy={i===1?153:202} r="49" fill="url(#surface)" stroke={ink} strokeWidth="3"/>
        <path d={'M'+(x-80)+' 390v-36a80 80 0 01160 0v36Z'} fill="#194257" stroke={ink} strokeWidth="3"/>
      </g>;
    }) : <g opacity={enter(p)} transform={move()}>
      <path d="M149 336L302 197L433 292L613 128" stroke={ink} fill="none" strokeWidth="13"
        strokeLinecap="round" strokeDasharray="680" strokeDashoffset={680*(1-smooth(p))}/>
      {[{x:149,y:336},{x:302,y:197},{x:433,y:292},{x:613,y:128}].map((a,i)=>
        <g key={i} opacity={enter(p,i*.09)}>
          <circle cx={a.x} cy={a.y} r="32" fill="#123146" stroke={ink} strokeWidth="5"/>
          <circle cx={a.x} cy={a.y} r="10" fill={ink}/>
        </g>)}
      <text x="400" y="426" textAnchor="middle" fill={ink} fontSize="21" letterSpacing="6">CERITA</text>
    </g>}
  </svg>;
};
