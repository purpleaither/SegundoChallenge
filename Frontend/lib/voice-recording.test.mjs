import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require=createRequire(import.meta.url),ts=require('typescript'),Module=require('node:module');
require.extensions['.ts']=(module,filename)=>module._compile(ts.transpileModule(readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,filename);
let slots=[],cursor=0,effects=[],first=true;
const hooks={
 useState(initial){const i=cursor++;if(first)slots[i]=initial;return [slots[i],value=>slots[i]=value];},
 useRef(initial){const i=cursor++;if(first)slots[i]={current:initial};return slots[i];},
 useEffect(effect){if(first)effects.push(effect);}
};
const load=Module._load;
Module._load=function(name,...args){if(name==='react')return hooks;if(name==='@/lib/server-voice-input')return require('./server-voice-input.ts');return load.call(this,name,...args);};
const {useVoiceInput}=require('../app/hooks/use-voice-input.ts');
const tick=()=>new Promise(r=>setImmediate(r));
function setup(getStream){
 slots=[];cursor=0;effects=[];first=true;let received=[],capture,closed=0;
 globalThis.window={isSecureContext:true};
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:getStream}}});
 const node=()=>({connect(){},disconnect(){}});
 class Context {
  constructor(){this.sampleRate=16000;this.state='running';this.destination={};this.audioWorklet={addModule:async()=>{}};}
  async resume(){} async close(){closed++;this.state='closed';}
  createMediaStreamSource(){return node();} createGain(){return {...node(),gain:{value:1}};}
 }
 class Capture {
  constructor(){capture=this;this.port={postMessage:()=>queueMicrotask(()=>this.port.onmessage?.({data:{type:'flushed'}})),close(){},onmessage:null};}
  connect(){} disconnect(){}
 }
 globalThis.AudioContext=Context;globalThis.AudioWorkletNode=Capture;
 const render=()=>{cursor=0;const hook=useVoiceInput(t=>received.push(t));if(first){first=false;const pending=effects;effects=[];for(const fn of pending)effects.push(fn());}return hook;};
 render();
 return {render,received,push:frames=>capture.port.onmessage?.({data:{type:'samples',samples:new Float32Array(frames)}}),closed:()=>closed,dispose:()=>effects.forEach(fn=>fn?.())};
}
function stream(){let stopped=0;const track={stop(){stopped++;},onended:null};return {getTracks:()=>[track],getAudioTracks:()=>[track],stopped:()=>stopped};}
test('shows previews while recording and revises instead of duplicating text',async()=>{
 const mic=stream(),c=setup(async()=>mic);let calls=0;globalThis.fetch=async()=>Response.json({text:++calls===1?'sobre renda':'sobre renda e família'});
 await c.render().start('Dúvida');assert.equal(c.render().status,'recording');c.push(40000);await tick();
 assert.deepEqual(c.received,['Dúvida sobre renda']);assert.equal(c.render().status,'recording');c.push(16000);c.render().stop();assert.ok(mic.stopped());await tick();
 assert.equal(c.received.at(-1),'Dúvida sobre renda e família');assert.equal(c.render().status,'idle');assert.ok(c.closed());c.dispose();
});
test('cancelling a pending permission releases a late microphone stream',async()=>{
 let grant;const mic=stream(),c=setup(()=>new Promise(r=>grant=r));const starting=c.render().start('');await tick();c.render().cancel();grant(mic);await starting;
 assert.equal(c.render().status,'idle');assert.ok(mic.stopped());assert.deepEqual(c.received,[]);c.dispose();
});
test('navigation cancellation discards a late transcription',async()=>{
 let finish;const c=setup(async()=>stream());globalThis.fetch=()=>new Promise(r=>finish=r);
 await c.render().start('');c.push(40000);await tick();c.render().cancel();finish(Response.json({text:'Resultado atrasado'}));await tick();assert.deepEqual(c.received,[]);assert.equal(c.render().status,'idle');c.dispose();
});
test('short recordings are transcribed on stop and microphone is released',async()=>{
 const mic=stream(),c=setup(async()=>mic);globalThis.fetch=async()=>Response.json({text:'Saúde'});
 await c.render().start('');c.push(16000);assert.deepEqual(c.received,[]);c.render().stop();await tick();assert.equal(c.received.at(-1),'Saúde');assert.ok(mic.stopped());assert.equal(c.render().status,'idle');c.dispose();
});
