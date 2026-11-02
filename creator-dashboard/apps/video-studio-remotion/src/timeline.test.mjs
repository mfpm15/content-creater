import assert from 'node:assert/strict';
import test from 'node:test';
import {validateManifest} from './timeline.mjs';

const example=()=>({version:1,width:320,height:568,fps:30,totalFrames:60,topic:'Studio',
  brand:{background:'#080f20',accent:'#22d3ee',text:'#ffffff',wordmark:'Studio',font:'Arial'},
  shots:[{id:'s1',startFrame:0,endFrame:60,title:'A complete thought',subject:'25%',family:'data',camera:'push-in',strength:.5,lighting:'soft',transition:'fade'}],
  captions:[{startFrame:0,endFrame:60,text:'Not 20, but 25 percent.'}]});

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
