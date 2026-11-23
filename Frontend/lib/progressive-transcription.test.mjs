import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { ProgressiveTranscriber, pcmWav } from './server-voice-input.ts';
const tick=()=>new Promise(r=>setImmediate(r));
test('WAV snapshots have correct sample rate, clipping and lengths',async()=>{
 const blob=pcmWav([new Float32Array([-2,0,2,0.5])],16000,3),view=new DataView(await blob.arrayBuffer());
 assert.equal(blob.type,'audio/wav');assert.equal(blob.size,50);assert.equal(view.getUint32(24,true),16000);assert.equal(view.getUint32(40,true),6);
 assert.equal(view.getInt16(44,true),-32768);assert.equal(view.getInt16(48,true),32767);
});
test('serializes requests, keeps full context and finalizes trailing speech',async()=>{
 const requests=[],updates=[];
 const p=new ProgressiveTranscriber(16000,text=>updates.push(text),(blob,signal)=>new Promise(resolve=>requests.push({blob,resolve,signal})));
 p.push(new Float32Array(40000));assert.equal(requests.length,1);p.push(new Float32Array(32000));assert.equal(requests.length,1);
 requests[0].resolve('Quero');await tick();assert.equal(requests.length,2);assert.ok(requests[1].blob.size>requests[0].blob.size);
 p.push(new Float32Array(8000));const final=p.finish();requests[1].resolve('Quero ajuda');await tick();assert.equal(requests.length,3);
 requests[2].resolve('Quero ajuda com moradia');assert.equal(await final,'Quero ajuda com moradia');assert.equal(updates.at(-1),'Quero ajuda com moradia');p.cancel();
});
test('final pass always revises a preview, cancelled results never update text',async()=>{
 let finish;const updates=[];const p=new ProgressiveTranscriber(16000,t=>updates.push(t),()=>new Promise(r=>finish=r));
 p.push(new Float32Array(40000));p.cancel();finish('ignorar');await tick();assert.deepEqual(updates,[]);
 let calls=0;const q=new ProgressiveTranscriber(16000,()=>{},async()=>{calls++;return 'Pronto';});q.push(new Float32Array(40000));await tick();assert.equal(await q.finish(),'Pronto');assert.equal(calls,2);q.cancel();
});
test('retries failed preview at finish and does not transcribe silence automatically',async()=>{
 let calls=0;const p=new ProgressiveTranscriber(16000,()=>{},async()=>{if(++calls===1)throw Error('offline');return 'Texto';});
 p.push(new Float32Array(40000));await tick();assert.equal(await p.finish(),'Texto');p.cancel();
 const empty=new ProgressiveTranscriber(16000,()=>{});await assert.rejects(empty.finish(),/Não há áudio/);empty.cancel();
});
test('worklet mixes channels and flushes the last partial buffer exactly once',()=>{
 let Processor;const messages=[];
 class Base{constructor(){this.port={postMessage:message=>messages.push(message)};}}
 vm.runInNewContext(readFileSync(new URL('../public/voice-capture.worklet.js',import.meta.url),'utf8'),{AudioWorkletProcessor:Base,Float32Array,registerProcessor:(_,ctor)=>Processor=ctor});
 const p=new Processor();p.process([[new Float32Array([1,0.5]),new Float32Array([-1,0.5])]]);p.port.onmessage({data:'flush'});
 assert.equal(messages[0].samples.length,2);assert.deepEqual([...messages[0].samples],[0,0.5]);assert.equal(messages[1].type,'flushed');p.process([[new Float32Array([1])]]);assert.equal(messages.length,2);
});
