import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url), ts = require('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
const { ServerSpeechOutput, fetchTtsAudio, ttsSegments } = require('./server-speech-output.ts');
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup() {
  const states=[], audios=[], revoked=[]; let fetched=0;
  const controller=new ServerSpeechOutput({
    fetchAudio:async()=>{fetched++;return new Blob(['a'.repeat(80)]);},
    createAudio:()=>{const a={play:async()=>a.onplaying?.(),pause(){},load(){},removeAttribute(){}};audios.push(a);return a;},
    createUrl:()=>`blob:${audios.length}`,revokeUrl:url=>revoked.push(url)
  },state=>states.push(state));
  return {controller,states,audios,revoked,fetched:()=>fetched};
}
test('pause, resume, replay cache and stop release audio',async()=>{
 const c=setup();c.controller.play('a','Olá.');await tick();assert.equal(c.states.at(-1).status,'speaking');
 c.controller.pause();assert.equal(c.states.at(-1).status,'paused');c.controller.resume();await tick();assert.equal(c.states.at(-1).status,'speaking');
 c.controller.play('a','Olá.');await tick();assert.equal(c.fetched(),1);assert.equal(c.revoked.length,1);
 c.controller.stop();assert.equal(c.states.at(-1).status,'idle');assert.equal(c.revoked.length,2);
 c.controller.reset();c.controller.play('a','Olá.');await tick();assert.equal(c.fetched(),2);c.controller.dispose();
});
test('plays chunks in order and ignores stale callbacks',async()=>{
 const c=setup();const text='Uma orientação sobre benefícios. '.repeat(25);c.controller.play('a',text);await tick();const stale=c.audios[0].onended;
 for(let i=0;i<ttsSegments(text).length;i++){c.audios[i].onended();await tick();}
 assert.equal(c.states.at(-1).status,'idle');c.controller.play('b','Outro texto.');await tick();stale();await tick();assert.equal(c.states.at(-1).id,'b');c.controller.dispose();
});
test('cancels pending generation without starting stale playback',async()=>{
 let finish;const states=[];const c=new ServerSpeechOutput({fetchAudio:()=>new Promise(r=>finish=r),createAudio:()=>{throw Error('stale');},createUrl:()=>'',revokeUrl(){}},s=>states.push(s));
 c.play('a','Texto.');c.stop();finish(new Blob(['a'.repeat(80)]));await tick();assert.equal(states.at(-1).status,'idle');assert.equal(states.at(-1).error,'');
});
test('validates HTTP response and cancellation',async()=>{
 const signal=new AbortController().signal;
 await assert.rejects(fetchTtsAudio('Olá',signal,async()=>new Response('bad',{status:503})),/gerar/);
 await assert.rejects(fetchTtsAudio('Olá',signal,async()=>new Response('html')),/válido/);
 const controller=new AbortController();controller.abort();await assert.rejects(fetchTtsAudio('Olá',controller.signal),{name:'AbortError'});
 const blob=await fetchTtsAudio('Olá',signal,async()=>new Response('a'.repeat(80),{headers:{'Content-Type':'audio/wav'}}));assert.equal(blob.size,80);
 assert.ok(ttsSegments('a'.repeat(1400)).every(x=>x.length<=600));
});
