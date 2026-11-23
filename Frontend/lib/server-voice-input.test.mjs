import assert from 'node:assert/strict';
import test from 'node:test';
import { appendTranscript, transcribeAudio, AUDIO_LIMIT_BYTES } from './server-voice-input.ts';

test('appends to draft without sending and respects input limit',()=>{
 assert.deepEqual(appendTranscript('Minha dúvida', 'sobre moradia.'),{text:'Minha dúvida sobre moradia.',truncated:false});
 const result=appendTranscript('a'.repeat(990),'b'.repeat(50));assert.equal(result.text.length,1000);assert.equal(result.truncated,true);
});
test('posts audio to STT and returns trimmed transcription',async()=>{
 const blob=new Blob(['recording'],{type:'audio/webm'});
 const text=await transcribeAudio(blob,new AbortController().signal,async(url,options)=>{
  assert.equal(url,'/api/stt');assert.equal(options.body,blob);assert.equal(options.headers['Content-Type'],'audio/webm');
  return Response.json({text:' Preciso de apoio. '});
 });assert.equal(text,'Preciso de apoio.');
});
test('handles silence, bad contract, busy service and oversized input',async()=>{
 const signal=new AbortController().signal,blob=new Blob(['audio']);
 assert.equal(await transcribeAudio(blob,signal,async()=>Response.json({text:''})), '');
 await assert.rejects(transcribeAudio(blob,signal,async()=>Response.json({wrong:true})),/inválida/);
 await assert.rejects(transcribeAudio(blob,signal,async()=>new Response('',{status:429})),/ocupada/);
 await assert.rejects(transcribeAudio(new Blob([]),signal),/Não há áudio/);
 await assert.rejects(transcribeAudio(new Blob([new Uint8Array(AUDIO_LIMIT_BYTES+1)]),signal),/grande/);
});
