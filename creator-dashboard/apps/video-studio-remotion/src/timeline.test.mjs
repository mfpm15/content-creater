import assert from 'node:assert/strict';
import test from 'node:test';
import {literalNumbers,validateManifest} from './timeline.mjs';
import {treatmentFor} from './visual-treatment.mjs';

const example=()=>({version:1,width:320,height:568,fps:30,totalFrames:60,topic:'Studio',
  brand:{background:'#080f20',accent:'#22d3ee',text:'#ffffff',wordmark:'Studio',font:'Arial'},
  shots:[{id:'s1',startFrame:0,endFrame:60,title:'A complete thought',subject:'25%',family:'data',camera:'push-in',strength:.5,lighting:'soft',transition:'fade'}],
  captions:[{startFrame:0,endFrame:60,text:'Not 20, but 25 percent.'}]});

test('numeric labels retain signs and never extract a tail from currency text',()=>{
  assert.deepEqual(literalNumbers('-3,5% +2.0 25%'),['-3,5%','+2.0','25%']);
  assert.deepEqual(literalNumbers('Rp2.000 Rp-3,5'),[]);
});

test('valid timeline remains unchanged and text is data',()=>{
  const value=example();value.shots[0].title='</script><img src=x>';
  assert.equal(validateManifest(value),value);
});
test('gaps, overlap, short coverage and duplicate IDs fail',()=>{
  for(const mutate of [v=>v.shots[0].startFrame=1,v=>v.shots[0].endFrame=59,v=>v.shots[0].endFrame=61,
    v=>v.shots.push({...v.shots[0],startFrame:60,endFrame:90}),v=>v.shots[0].endFrame=0]){
    const value=example();mutate(value);assert.throws(()=>validateManifest(value));
  }
});
test('unknown script, URL, CSS, invalid numeric and prototype fields fail',()=>{
  for(const mutate of [v=>v.script='alert(1)',v=>v.assetUrl='https://bad.test',v=>v.shots[0].camera='eval(1)',
    v=>v.shots[0].strength=NaN,v=>v.shots[0].strength=true,v=>v.brand.accent='url(https://bad.test)',
    v=>v.brand.font='https://bad.test/font',v=>v.width=Infinity,v=>v.fps=3000,
    v=>Object.assign(v,JSON.parse('{"__proto__":{}}'))]){
    const value=example();mutate(value);assert.throws(()=>validateManifest(value));
  }
});
test('captions cannot overlap or exceed approved frames',()=>{
  for(const mutate of [v=>v.captions.push({startFrame:20,endFrame:40,text:'Overlap'}),v=>v.captions[0].endFrame=61,
    v=>v.captions[0].text='x'.repeat(501)]){
    const value=example();mutate(value);assert.throws(()=>validateManifest(value));
  }
});
test('approved diagram labels are preserved and invalid structures rejected',()=>{
  const value=example();value.shots[0].diagram={kind:'process',labels:['Riset','Review','Terbit']};
  assert.deepEqual(validateManifest(value).shots[0].diagram.labels,['Riset','Review','Terbit']);
  for(const diagram of [{kind:'process',labels:['Only one']},{kind:'comparison',labels:['a','b','c']},
    {kind:'process',labels:['','b']},{kind:'process',labels:['a','x'.repeat(49)]},{kind:'process',labels:['a','b'],url:'https://bad.test'}]){
    value.shots[0].diagram=diagram;assert.throws(()=>validateManifest(value));
  }
});
test('60fps supports 600 seconds and rejects frames beyond the duration bound',()=>{
  const value=example();value.fps=60;value.totalFrames=36000;value.shots[0].endFrame=36000;
  assert.equal(validateManifest(value).fps,60);
  value.totalFrames=36001;value.shots[0].endFrame=36001;assert.throws(()=>validateManifest(value));
  value.fps=30;value.totalFrames=18001;value.shots[0].endFrame=18001;assert.throws(()=>validateManifest(value));
});


test('semantic shot art uses approved headlines instead of repeating generic circles',()=>{
  const expected=[
    ['2 November', 'calendar'],
    ['Penyimpanan darah', 'medical'],
    ['Tiga fasilitas', 'facilities'],
    ['Layanan bisa terganggu', 'warning'],
    ['Siber sama pentingnya', 'security'],
    ['Ikuti info resmi', 'verified'],
  ];
  for(const [title,kind] of expected){
    assert.equal(treatmentFor({title,subject:'',family:'concept'}),kind,title);
  }
  assert.equal(treatmentFor({title:'Tiga fasilitas',subject:'Penyimpanan darah',family:'concept'}),'facilities');
  assert.equal(treatmentFor({title:'Hasil 25%',subject:'',family:'data'}),'data');
  assert.equal(treatmentFor({title:'Cerita umum',subject:'',family:'concept'}),'story');
});

test('video layout templates are validated and backward compatible',()=>{
  for (const layout of ['editorial','headline','split','poster','center']) {
    const value=example();value.layout=layout;assert.equal(validateManifest(value).layout,layout);
  }
  const bad=example();bad.layout='<script>';assert.throws(()=>validateManifest(bad));
  assert.equal(validateManifest(example()).layout,undefined);
});

test('motion effects use a strict allowlist',()=>{
  for(const effect of ['minimal','cinematic','technical','kinetic','calm','urgent']){
    const value=example();value.effect=effect;assert.equal(validateManifest(value).effect,effect);
  }
  const bad=example();bad.effect='url(javascript:evil)';assert.throws(()=>validateManifest(bad));
});


test('shot artwork only accepts trusted local media filenames',()=>{
  const ok=example();
  ok.shots[0].assetFile='media/0123456789abcdef0123456789abcdef.jpg';
  assert.equal(validateManifest(ok).shots[0].assetFile,ok.shots[0].assetFile);
  for(const badFile of ['../../evil.png','https://example.com/x.jpg','media/wrong.svg',
    'media/0123456789abcdef0123456789abcdef.jpg?x=1','media/../evil.png']){
    const bad=example();bad.shots[0].assetFile=badFile;
    assert.throws(()=>validateManifest(bad));
  }
});

test('motif is an allowlisted illustration key',()=>{
  const ok=example();ok.shots[0].motif='elephant';
  assert.equal(validateManifest(ok).shots[0].motif,'elephant');
  const bad=example();bad.shots[0].motif='<script>';assert.throws(()=>validateManifest(bad));
});

test('caption styles and authentic cue ranges are validated',()=>{
  for (const style of ['clean','pop','pill','outline','highlight','karaoke']) {
    const value=example();value.captionStyle=style;
    assert.equal(validateManifest(value).captionStyle,style);
  }
  const valid=example();
  valid.captionStyle='highlight';
  const c=valid.captions[0];
  c.wordFrames=[{text:'kata',startFrame:c.startFrame,endFrame:c.endFrame}];
  assert.equal(validateManifest(valid).captions[0].wordFrames.length,1);
  const invalid=example();invalid.captionStyle='<script>';assert.throws(()=>validateManifest(invalid));
  for(const bad of ['https://example.com','../../file']) {
    const broken=example();broken.captions[0].wordFrames=[{text:bad,startFrame:0,endFrame:900000}];
    assert.throws(()=>validateManifest(broken));
  }
});
