import React from 'react';
import {AbsoluteFill, Composition, interpolate, registerRoot, useCurrentFrame, useVideoConfig} from 'remotion';
import {literalNumbers, validateManifest} from './timeline.mjs';
import type {Shot, StudioProps} from './types';

// Original procedural artwork. Numbers are literal labels from narration/title,
// never fabricated bar values or performance predictions.
const Illustration: React.FC<{shot: Shot; progress: number; accent: string}> = ({shot, progress, accent}) => {
  const numbers = literalNumbers(shot.subject).slice(0,3);
  const diagram=shot.diagram;
  const editorial=(shot.subject || shot.title).match(/.{1,28}(?:\s|$)|.{1,28}/g) || [''];
  return <svg viewBox="0 0 800 500" width="100%" height="100%" aria-hidden="true">
    {diagram ? <>
      {diagram.kind==='process' && <path d="M400 60 V440" fill="none" stroke={accent} strokeWidth="3" opacity=".4" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress}/>}
      {diagram.labels.map((label,i)=>{
        const process=diagram.kind==='process';
        const x=process?400:210+i*380;
        const y=process?70+i*360/(diagram.labels.length-1):250;
        const w=process?650:330;
        const words=label.match(/.{1,18}(?:\s|$)|.{1,18}/g) || [label];
        return <g key={i} transform={`translate(${x},${y})`} opacity={interpolate(progress,[i*.12,i*.12+.18],[.25,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}>
          <rect x={-w/2} y={process?-34:-120} width={w} height={process?68:240} rx="16" fill="#152131" stroke={accent} strokeWidth="2"/>
          <text textAnchor="middle" fill="currentColor" fontSize={process?Math.min(25,560/(label.length*.65)):25} fontWeight="600">
            {(process?[label]:words).map((line,j)=><tspan key={j} x="0" dy={j===0?(process?8:-(words.length-1)*18):36}>{line}</tspan>)}
          </text>
        </g>;
      })}
    </> : shot.family === 'data' && numbers.length ? <>
      {numbers.map((number,i)=><g key={i} transform={`translate(${400+(i-(numbers.length-1)/2)*235},250)`}>
        <circle r="100" fill={accent} fillOpacity=".1" stroke={accent} strokeWidth="2"/>
        <text textAnchor="middle" dy=".35em" fill="currentColor" fontSize={Math.min(52,300/number.length)} fontWeight="700">{number}</text>
      </g>)}
    </> : <>
      <path d="M100 110 H700 M100 390 H700" stroke={accent} strokeWidth="3"/>
      <text x="400" y="260" textAnchor="middle" fill="currentColor" fontSize="38" fontWeight="600">{editorial.map((line,j)=><tspan key={j} x="400" dy={j===0?-(editorial.length-1)*22:44}>{line}</tspan>)}</text>
    </>}
  </svg>;
};

export const Studio: React.FC<StudioProps> = props => {
  const frame = useCurrentFrame();
  const rootRef=React.useRef<HTMLDivElement>(null);
  const titleRef=React.useRef<HTMLDivElement>(null);
  const artRef=React.useRef<HTMLDivElement>(null);
  const captionRef=React.useRef<HTMLDivElement>(null);
  const {width,height} = useVideoConfig();
  const shot = props.shots.find(s=>frame>=s.startFrame && frame<s.endFrame) || props.shots[props.shots.length-1];
  const index = props.shots.indexOf(shot);
  const local = frame-shot.startFrame;
  const length = shot.endFrame-shot.startFrame;
  const progress = Math.max(0,Math.min(1,local/Math.max(1,length-1)));
  const portrait = height>width;
  const scaleUnit = Math.min(width,height)/1080;
  const a = shot.strength;
  const camera = shot.camera;
  const scale = camera==='push-in' ? 1+progress*.12*a : camera==='pull-out' ? 1+(1-progress)*.12*a : 1;
  const x = camera==='pan-left' ? (1-2*progress)*3*a : camera==='pan-right' ? (2*progress-1)*3*a : 0;
  const rotation = camera==='orbit' ? (progress-.5)*6*a : 0;
  const edge = Math.min(10,Math.max(1,Math.floor(length/3)));
  const opacity = shot.transition==='cut' ? 1 : Math.min(index===0?1:(local+1)/edge,1,(length-local)/edge);
  const slide = shot.transition==='slide' ? (1-Math.min(1,local/edge))*width*.06 : 0;
  const caption = props.captions.find(c=>frame>=c.startFrame && frame<c.endFrame);
  const filter = shot.lighting==='soft' ? 'brightness(1.15) contrast(.85)' : shot.lighting==='dramatic' ? 'brightness(.82) contrast(1.35)' : 'none';
  React.useLayoutEffect(()=>{
    const root=rootRef.current?.getBoundingClientRect();
    // Remotion also mounts hidden calculator trees at y=-1,000,000 with zero
    // width. They are not the rendered composition and must never be measured.
    if(!root || root.width<1 || root.height<1 || root.bottom<=0 || root.right<=0 || root.top>=window.innerHeight || root.left>=window.innerWidth)return;
    if(titleRef.current)titleRef.current.style.fontSize=((portrait?88:70)*scaleUnit*Math.min(1,Math.sqrt(42/Math.max(42,shot.title.length))))+'px';
    if(captionRef.current)captionRef.current.style.fontSize=(40*scaleUnit)+'px';
    for(const [element,budget] of [[titleRef.current,.13],[captionRef.current,.12]] as const){
      if(!element)continue;
      let fs=parseFloat(getComputedStyle(element).fontSize);
      while((element.scrollHeight>height*budget || element.scrollWidth>element.clientWidth+1) && fs>14*scaleUnit){fs-=scaleUnit;element.style.fontSize=fs+'px';}
    }
    if(local<edge || local>=length-edge)return; // intentional entry/exit motion
    const relative=(box: DOMRect | undefined)=>box?{left:(box.left-root.left)*width/root.width,right:(box.right-root.left)*width/root.width,
      top:(box.top-root.top)*height/root.height,bottom:(box.bottom-root.top)*height/root.height}:undefined;
    const title=relative(titleRef.current?.getBoundingClientRect()),art=relative(artRef.current?.getBoundingClientRect()),sub=relative(captionRef.current?.getBoundingClientRect());
    const issues:string[]=[];
    if(title && art && title.bottom>art.top)issues.push('title_illustration_overlap');
    if(sub && art && sub.top<art.bottom)issues.push('caption_illustration_overlap');
    for(const box of [title,sub])if(box && (box.left<width*.05 || box.right>width*.86+1 || box.top<height*.1 || box.bottom>height*.78+1))issues.push('text_outside_common_safe_area');
    console.log('STUDIO_LAYOUT:'+JSON.stringify({frame,scene:shot.id,issues:[...new Set(issues)],
      ...(local===Math.floor((length-1)/2)?{geometry:{title,art,caption:sub,viewport:[window.innerWidth,window.innerHeight]}}:{})}));
  },[frame,width,height,shot.id]);
  return <div ref={rootRef} style={{position:'absolute',inset:0,background:props.brand.background,color:props.brand.text,fontFamily:props.brand.font,overflow:'hidden'}}>
    <AbsoluteFill style={{background:`radial-gradient(ellipse at 75% 20%, ${props.brand.accent}25, transparent 60%)`}}/>
    <AbsoluteFill style={{padding:`${height*.11}px ${width*.16}px ${height*.24}px ${width*.08}px`,opacity,transform:`translateX(${slide}px)`}}>
      <div style={{display:'flex',justifyContent:'space-between',fontSize:24*scaleUnit,letterSpacing:3*scaleUnit,color:props.brand.accent,fontWeight:700}}><span>{String(index+1).padStart(2,'0')} / {String(props.shots.length).padStart(2,'0')}</span><span style={{fontSize:20*scaleUnit,letterSpacing:0}}>{props.brand.wordmark}</span></div>
      <div ref={titleRef} style={{fontSize:(portrait?88:70)*scaleUnit*Math.min(1,Math.sqrt(42/Math.max(42,shot.title.length))),lineHeight:1.12,fontWeight:800,marginTop:height*.035,maxWidth:width*.76,overflowWrap:'anywhere'}}>{shot.title}</div>
      <div ref={artRef} style={{position:'absolute',left:'8%',right:'16%',top:'28%',height:portrait?'35%':'30%',transform:`translateX(${x}%) scale(${scale}) rotate(${rotation}deg)`,filter}}>
        <Illustration shot={shot} progress={progress} accent={props.brand.accent}/>
      </div>
      {caption && <div ref={captionRef} style={{position:'absolute',left:'8%',right:'16%',bottom:'24%',padding:`${24*scaleUnit}px ${30*scaleUnit}px`,borderLeft:`${5*scaleUnit}px solid ${props.brand.accent}`,fontSize:40*scaleUnit,lineHeight:1.35,background:props.brand.background,overflowWrap:'anywhere'}}>{caption.text}</div>}
    </AbsoluteFill>
    <div style={{position:'absolute',left:0,bottom:0,height:4*scaleUnit,width:`${(frame+1)/props.totalFrames*100}%`,background:props.brand.accent}}/>
  </div>;
};

const defaults: StudioProps={version:1,width:1080,height:1920,fps:30,totalFrames:30,topic:'Video Studio',
  brand:{background:'#080f20',accent:'#22d3ee',text:'#ffffff',wordmark:'',font:'Arial'},
  shots:[{id:'scene-1',startFrame:0,endFrame:30,title:'Video Studio',subject:'',family:'concept',camera:'locked',strength:.5,lighting:'legacy',transition:'fade'}],captions:[]};
const Root: React.FC=()=> <Composition id="StudioMotion" component={Studio} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={defaults}
  calculateMetadata={({props})=>{const p=validateManifest(props);return {width:p.width,height:p.height,fps:p.fps,durationInFrames:p.totalFrames,props:p};}}/>;
registerRoot(Root);
