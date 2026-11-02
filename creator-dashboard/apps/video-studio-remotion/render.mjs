import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {validateManifest} from './src/timeline.mjs';

const [manifestFile, output, browserExecutable] = process.argv.slice(2);
if (process.argv.length!==5 || !manifestFile || !output || !browserExecutable) throw new Error('Expected manifest, output and installed browser');
const stat=fs.lstatSync(manifestFile);
if (!stat.isFile() || stat.isSymbolicLink() || stat.size>2000000 || !fs.existsSync(browserExecutable)) throw new Error('Invalid local renderer input');
const inputProps=validateManifest(JSON.parse(fs.readFileSync(manifestFile,'utf8')));
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'video-studio-remotion-'));
try {
  const layout=new Map();
  const serveUrl=await bundle({entryPoint:fileURLToPath(new URL('./src/Studio.tsx',import.meta.url)),outDir:path.join(directory,'bundle'),publicDir:null});
  const options={serveUrl,id:'StudioMotion',inputProps,browserExecutable,
    chromiumOptions:{disableWebSecurity:false},
    onBrowserLog:log=>{if(log.text.startsWith('STUDIO_LAYOUT:')){const row=JSON.parse(log.text.slice(14));layout.set(row.frame,row);}},
    onBrowserDownload:()=>{throw new Error('Install Chrome or Edge; automatic browser download disabled');}};
  const composition=await selectComposition(options);
  let last=-1;
  await renderMedia({...options,composition,outputLocation:output,codec:'h264',pixelFormat:'yuv420p',colorSpace:'bt709',imageFormat:'png',crf:18,
    concurrency:1,overwrite:true,onProgress:({progress})=>{const step=Math.floor(progress*100);if(step!==last){last=step;process.stdout.write(JSON.stringify({progress})+'\n');}}});
  const samples=[...new Set(Array.from({length:Math.min(6,inputProps.shots.length)},(_,i)=>Math.round(i*(inputProps.shots.length-1)/Math.max(1,Math.min(6,inputProps.shots.length)-1))))];
  const frames=[];
  for (const index of samples) {
    const shot=inputProps.shots[index],frame=Math.floor((shot.startFrame+shot.endFrame-1)/2);
    const name=`review-frame-${frames.length}.png`;
    await renderStill({...options,composition,frame,imageFormat:'png',output:path.join(path.dirname(output),name)});
    frames.push({file:name,frame,scene:shot.id});
  }
  const repeat=path.join(directory,'repeat.png');
  await renderStill({...options,composition,frame:frames[0].frame,imageFormat:'png',output:repeat});
  const digest=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  if(digest(repeat)!==digest(path.join(path.dirname(output),frames[0].file)))throw new Error('Remotion repeated frame differs');
  process.stdout.write(JSON.stringify({frames,deterministic_repeat:true,layout:{observed_frames:layout.size,sample_geometry:[...layout.values()].filter(row=>row.geometry).slice(0,6),issues:[...new Map([...layout.values()].flatMap(row=>row.issues.map(code=>[row.scene+':'+code,{scene:row.scene,code}]))).values()]}})+'\n');
} catch(error) {
  fs.rmSync(output,{force:true});
  throw error;
} finally { fs.rmSync(directory,{recursive:true,force:true}); }
