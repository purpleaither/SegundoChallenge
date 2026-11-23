import assert from 'node:assert/strict';
import test from 'node:test';
import { SpeechOutput, speechChunks } from './speech-output.ts';
import { transcriptText, voiceInputError } from './voice-input.ts';

function setup() {
  const utterances = [];
  const states = [];
  let cancelled = 0, paused = 0, resumed = 0;
  const engine = {
    getVoices: () => [{ name: 'Voz brasileira', lang: 'pt-BR' }],
    speak: utterance => { utterances.push(utterance); utterance.onstart?.(); },
    cancel: () => { cancelled++; }, pause: () => { paused++; }, resume: () => { resumed++; }
  };
  const controller = new SpeechOutput(engine, text => ({ text }), state => states.push(state));
  return { controller, utterances, states, counts: () => ({ cancelled, paused, resumed }) };
}

test('reads all chunks in order using Portuguese', () => {
  const text = 'Uma resposta com valores de R$ 1.518,00 e critérios de acesso. '.repeat(12).trim();
  const ctx = setup();
  ctx.controller.play('a', text);
  for (let i = 0; i < ctx.utterances.length; i++) ctx.utterances[i].onend();
  assert.equal(ctx.utterances.map(u => u.text).join(' '), text);
  assert.ok(ctx.utterances.every(u => u.lang === 'pt-BR' && u.voice.lang === 'pt-BR'));
  assert.equal(ctx.states.at(-1).status, 'idle');
});
test('pause and resume change the same playback', () => {
  const ctx = setup(); ctx.controller.play('a', 'Resposta.'); ctx.controller.pause();
  assert.equal(ctx.states.at(-1).status, 'paused');
  ctx.controller.resume(); assert.equal(ctx.states.at(-1).status, 'speaking');
  assert.deepEqual(ctx.counts(), { cancelled: 0, paused: 1, resumed: 1 });
});
test('stopping or replacing a response prevents stale callbacks from continuing it', () => {
  const ctx = setup(); ctx.controller.play('a', 'Primeira resposta. '.repeat(40));
  const old = ctx.utterances[0]; ctx.controller.play('b', 'Nova resposta.');
  const count = ctx.utterances.length; old.onend(); old.onerror();
  assert.equal(ctx.utterances.length, count);
  assert.equal(ctx.states.at(-1).id, 'b');
  ctx.controller.stop(); ctx.utterances.at(-1).onend();
  assert.equal(ctx.states.at(-1).status, 'idle');
  assert.equal(ctx.counts().cancelled, 2);
});
test('reports synthesis errors and stops on disposal without updating UI', () => {
  const ctx = setup(); ctx.controller.play('a', 'Resposta.'); ctx.utterances[0].onerror();
  assert.ok(ctx.states.at(-1).error); assert.equal(ctx.states.at(-1).status, 'idle');
  ctx.controller.play('b', 'Outra resposta.'); const count = ctx.states.length;
  ctx.controller.dispose(); ctx.utterances.at(-1).onend();
  assert.equal(ctx.states.length, count);
});
test('empty text does not start speech and transcriptions are not duplicated', () => {
  assert.deepEqual(speechChunks('   '), []);
  assert.equal(transcriptText([[{ transcript: 'Quais benefícios' }], [{ transcript: 'posso receber?' }]]), 'Quais benefícios posso receber?');
  assert.equal(transcriptText([[{ transcript: 'Quais benefícios posso receber?' }]]), 'Quais benefícios posso receber?');
});
test('permission, silence and network failures have actionable messages', () => {
  assert.match(voiceInputError('not-allowed'), /negado/);
  assert.match(voiceInputError('no-speech'), /ouvir/);
  assert.match(voiceInputError('network'), /conexão/);
});

test('replay of a paused response restarts at its first chunk and releases pause', () => {
  const ctx = setup(); const text = 'Começo da resposta. '.repeat(30);
  ctx.controller.play('a', text); const first = ctx.utterances[0];
  ctx.controller.pause(); ctx.controller.play('a', text);
  assert.equal(ctx.utterances[1].text, first.text);
  assert.equal(ctx.states.at(-1).status, 'speaking');
  assert.equal(ctx.counts().resumed, 1);
  const count = ctx.utterances.length; first.onend();
  assert.equal(ctx.utterances.length, count);
});
test('a completed response can be replayed from the start', () => {
  const ctx = setup(); ctx.controller.play('a', 'Resposta inteira.');
  ctx.utterances[0].onend(); assert.equal(ctx.states.at(-1).status, 'idle');
  ctx.controller.play('a', 'Resposta inteira.');
  assert.equal(ctx.utterances[1].text, 'Resposta inteira.');
  assert.equal(ctx.states.at(-1).status, 'speaking');
});
