import React from 'react';
import {mix} from './Scenes';

/** Per-effect decorative layer. Pure function of time: deterministic, no assets, no randomness. */
const rnd=(i:number)=>{const x=Math.sin(i*127.1+311.7)*43758.5453;return x-Math.floor(x);};
type P={effect:string;accent:string;ink:string;t:number;width:number;height:number;unit:number;index:number;topic:string;light:boolean};

const wave=(w:number,base:number,amp:number,k:number,speed:number,t:number)=>{
  const n=28;let d=`M0 ${base}`;
  for(let i=0;i<=n;i++){const x=w*i/n;d+=` L${x} ${base+Math.sin(i*k+t*speed)*amp}`;}
  return d;
};

export const Decor:React.FC<P>=({effect,accent,ink,t,width,height,unit,index,topic,light})=>{
  const abs:React.CSSProperties={position:'absolute',pointerEvents:'none'};
  const soft=light?.55:1;
  const numeral=<div style={{...abs,right:-width*.03,top:height*.33,fontSize:height*.36,fontWeight:900,lineHeight:1,letterSpacing:-4*unit,
    color:'transparent',WebkitTextStroke:`${3*unit}px ${accent}`,opacity:.1*soft+Math.sin(t*.8)*.02,
    transform:`translateY(${Math.sin(t*.5+index)*10*unit}px)`}}>{String(index+1).padStart(2,'0')}</div>;
  let body:React.ReactNode=null;
  if(effect==='technical'){
    const cols=[.03,.93].flatMap((x,c)=>[0,1].map(r=>({x:x+(r?.045:0),c:c*2+r})));
    body=<>
      <div style={{...abs,inset:0,opacity:.5*soft,backgroundImage:`linear-gradient(${accent}2e 1px,transparent 1px),linear-gradient(90deg,${accent}2e 1px,transparent 1px)`,
        backgroundSize:`${70*unit}px ${70*unit}px`,backgroundPosition:`${t*10*unit}px ${t*14*unit}px`,
        WebkitMaskImage:'radial-gradient(ellipse at 50% 42%,#000 10%,transparent 78%)'}}/>
      {cols.map(({x,c})=><div key={c} style={{...abs,left:x*width,top:-height*.2+((t*(30+c*9)*unit)%(height*.4)),height:height*1.4,overflow:'hidden',
        fontFamily:'monospace',fontSize:15*unit,lineHeight:1.5,color:accent,opacity:.22*soft,writingMode:'vertical-rl' as const,letterSpacing:3*unit}}>
        {Array.from({length:70},(_,i)=>rnd(i+c*31)>.5?'1':'0').join(' ')}</div>)}
      {[[0,0],[1,0],[0,1],[1,1]].map(([r,b],i)=><div key={i} style={{...abs,[r?'right':'left']:width*.045,[b?'bottom':'top']:height*.04,width:64*unit,height:64*unit,
        borderColor:accent,borderStyle:'solid',borderWidth:`${b?0:4*unit}px ${r?4*unit:0}px ${b?4*unit:0}px ${r?0:4*unit}px`,opacity:.7}}/>)}
    </>;
  }else if(effect==='cinematic'){
    body=<>
      {[0,1].map(i=><div key={i} style={{...abs,left:-width*.2,top:height*(.18+i*.42),width:width*1.4,height:height*.2,
        background:`linear-gradient(90deg,transparent,${accent}${i?'26':'36'},transparent)`,transform:`rotate(${-24+i*6}deg) translateX(${Math.sin(t*.22+i*2)*width*.18}px)`,filter:`blur(${18*unit}px)`}}/>)}
      {Array.from({length:22},(_,i)=>{const k=1-((t*.03*(.5+rnd(i))+rnd(i+9))%1);
        return <div key={i} style={{...abs,left:rnd(i+3)*width,top:k*height,width:(2+rnd(i)*4)*unit,height:(2+rnd(i)*4)*unit,borderRadius:'50%',background:'#ffffff',opacity:.35*Math.sin(k*Math.PI)}}/>;})}
      <div style={{...abs,inset:0,background:'radial-gradient(ellipse at 50% 45%,transparent 55%,rgba(0,0,0,.45) 100%)'}}/>
      <div style={{...abs,left:0,right:0,top:0,height:height*.045,background:'rgba(0,0,0,.88)'}}/>
      <div style={{...abs,left:0,right:0,bottom:0,height:height*.045,background:'rgba(0,0,0,.88)'}}/>
    </>;
  }else if(effect==='kinetic'){
    body=<>
      {[0,1,2].map(i=><div key={i} style={{...abs,left:-width*.5,top:height*(.06+i*.31),width:width*2,height:height*.1,
        background:`${accent}${i===1?'2c':'18'}`,transform:`rotate(-14deg) translateX(${((t*(40+i*26)*unit)%(width*.9))*(i%2?1:-1)}px)`}}/>)}
      <div style={{...abs,right:-width*.18,top:height*.05,width:width*.55,height:width*.55,borderRadius:'50%',border:`${7*unit}px dashed ${accent}`,opacity:.3*soft+.1,transform:`rotate(${t*24}deg)`}}/>
      <div style={{...abs,left:-width*.12,bottom:height*.12,width:width*.34,height:width*.34,borderRadius:'50%',background:accent,opacity:.16*soft+.04,transform:`scale(${1+Math.sin(t*2.4)*.08})`}}/>
      <div style={{...abs,left:0,right:0,bottom:height*.06,height:height*.05,opacity:.35*soft+.1,
        backgroundImage:`repeating-linear-gradient(135deg,${accent} 0 ${16*unit}px,transparent ${16*unit}px ${42*unit}px)`,backgroundPosition:`${t*60*unit}px 0`}}/>
    </>;
  }else if(effect==='calm'){
    body=<>
      {[0,1,2].map(i=><div key={i} style={{...abs,left:rnd(i+20)*width*.8,top:height*(.12+i*.28),width:width*(.34+i*.08),height:width*(.34+i*.08),borderRadius:'50%',
        background:`radial-gradient(circle,${accent}${light?'30':'26'},transparent 68%)`,transform:`translate(${Math.sin(t*.35+i*2)*width*.05}px,${Math.cos(t*.3+i)*height*.03}px)`}}/>)}
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} style={{...abs,left:0,top:0}}>
        <path d={wave(width,height*.92,height*.012,.7,1.1,t)+` V${height} H0Z`} fill={accent} opacity={.14*soft+.04}/>
        <path d={wave(width,height*.94,height*.01,.9,-.9,t)+` V${height} H0Z`} fill={accent} opacity={.18*soft+.05}/>
        <path d={wave(width,height*.96,height*.008,1.1,1.5,t)+` V${height} H0Z`} fill={mix(accent,'#000000',.35)} opacity={.3}/>
      </svg>
    </>;
  }else if(effect==='urgent'){
    const label=(topic||'').toUpperCase().slice(0,48)+'   •   ';
    body=<>
      <div style={{...abs,left:0,right:0,top:0,height:height*.042,background:accent,overflow:'hidden',display:'flex',alignItems:'center'}}>
        <div style={{whiteSpace:'nowrap',fontWeight:900,fontSize:height*.02,letterSpacing:3*unit,color:'#111',transform:`translateX(${-((t*130*unit)%(width*1.2))}px)`}}>
          {label.repeat(10)}</div></div>
      <div style={{...abs,left:0,right:0,bottom:height*.012,height:height*.016,opacity:.9,
        backgroundImage:`repeating-linear-gradient(45deg,${accent} 0 ${18*unit}px,#111 ${18*unit}px ${36*unit}px)`,backgroundPosition:`${t*50*unit}px 0`}}/>
      <div style={{...abs,inset:0,background:`radial-gradient(ellipse at 50% 50%,transparent 60%,${accent}33 100%)`,opacity:.7+Math.sin(t*5)*.3}}/>
    </>;
  }else{
    body=<>
      {[.09,.91].map((y,i)=><div key={i} style={{...abs,left:width*.06,right:width*.06,top:height*y,height:2*unit,background:accent,opacity:.4*soft+.1}}/>)}
      {[.06,.94].map((x,i)=>[.09,.91].map((y,j)=><div key={i+'-'+j} style={{...abs,left:width*x-10*unit,top:height*y-10*unit,width:20*unit,height:20*unit,
        background:`linear-gradient(${accent},${accent}) center/100% 2px no-repeat,linear-gradient(${accent},${accent}) center/2px 100% no-repeat`,opacity:.7}}/>))}
      <div style={{...abs,left:width*.5-width*.42,top:height*.5-width*.42,width:width*.84,height:width*.84,borderRadius:'50%',border:`${2*unit}px solid ${accent}`,opacity:.1*soft+.04,transform:`rotate(${t*4}deg) scaleY(.92)`}}/>
    </>;
  }
  return <div style={{...abs,inset:0,overflow:'hidden',color:ink}}>{numeral}{body}</div>;
};
