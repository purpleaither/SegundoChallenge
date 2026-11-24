import assert from 'node:assert/strict'
import test from 'node:test'
import { dividirTextoParaFala, limparMarkdownParaFala } from './audio.ts'

test('removes Markdown markers while preserving the words for speech', () => {
  const plainText = limparMarkdownParaFala(
    '## Benefício\n- **Auxílio Gás**: *confirme os critérios* [no CRAS](https://gov.br).',
  )

  assert.equal(plainText, 'Benefício Auxílio Gás: confirme os critérios no CRAS.')
})

test('splits long speech into chunks accepted by the TTS service', () => {
  const text = Array.from({ length: 130 }, (_, index) => `palavra${index}`).join(' ')
  const chunks = dividirTextoParaFala(text)

  assert.ok(chunks.length > 1)
  assert.ok(chunks.every((chunk) => Array.from(chunk).length <= 500))
  assert.equal(chunks.join(' '), text)
})

test('keeps Unicode characters intact when splitting oversized words', () => {
  const text = '🙂'.repeat(501)
  const chunks = dividirTextoParaFala(text)

  assert.ok(chunks.every((chunk) => Array.from(chunk).length <= 500))
  assert.equal(chunks.join(''), text)
})
