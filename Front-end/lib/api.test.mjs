import assert from 'node:assert/strict'
import test from 'node:test'
import { perguntar, sintetizarAudio, transcreverAudio } from './api.ts'

test('sends typed questions to the multiagent API route', async () => {
  const originalFetch = globalThis.fetch
  let url
  let body
  globalThis.fetch = async (input, init) => {
    url = input
    body = init?.body
    return new Response(JSON.stringify({ answer: 'Resposta', benefits: [] }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    await perguntar('Qual benefício existe?')
    assert.equal(url, '/api/orientar')
    assert.deepEqual(JSON.parse(body), { question: 'Qual benefício existe?' })
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('uploads recorded audio to local speech transcription', async () => {
  const originalFetch = globalThis.fetch
  let url
  let contentType
  let uploadedAudio
  globalThis.fetch = async (input, init) => {
    url = input
    contentType = new Headers(init?.headers).get('Content-Type')
    uploadedAudio = init?.body
    return new Response(JSON.stringify({ text: 'Pergunta transcrita.' }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const audio = new Blob(['recording'], { type: 'audio/webm;codecs=opus' })
    assert.equal(await transcreverAudio(audio), 'Pergunta transcrita.')
    assert.equal(url, '/api/stt')
    assert.equal(contentType, 'audio/webm')
    assert.equal(uploadedAudio, audio)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('requests a WAV response from the local speech synthesis service', async () => {
  const originalFetch = globalThis.fetch
  let url
  let body
  globalThis.fetch = async (input, init) => {
    url = input
    body = init?.body
    return new Response(new Uint8Array([82, 73, 70, 70]), {
      headers: { 'Content-Type': 'audio/wav' },
    })
  }

  try {
    const audio = await sintetizarAudio('Resposta falada.')
    assert.equal(url, '/api/tts')
    assert.deepEqual(JSON.parse(body), { text: 'Resposta falada.' })
    assert.equal(audio.type, 'audio/wav')
  } finally {
    globalThis.fetch = originalFetch
  }
})
