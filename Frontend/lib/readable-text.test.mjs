import assert from 'node:assert/strict';
import test from 'node:test';
import { readingTerms, readingTopics } from './readable-text.ts';

test('preserves monetary values and legal references', () => {
  const text = 'Renda de até R$ 1.518,00. Consulte a Lei nº 14.601/2023.';
  assert.deepEqual(readingTopics(text), ['Renda de até R$ 1.518,00.', 'Consulte a Lei nº 14.601/2023.']);
});
test('does not break eligibility clauses or legal abbreviations', () => {
  assert.deepEqual(readingTopics('Art. 2º: renda inferior ao limite; ou outra condição prevista.'), ['Art. 2º: renda inferior ao limite; ou outra condição prevista.']);
});
test('keeps every condition and its original order', () => {
  assert.deepEqual(readingTopics('É preciso ter cadastro. Não há aprovação automática.'), ['É preciso ter cadastro.', 'Não há aprovação automática.']);
  assert.deepEqual(readingTopics('- Documento válido\n- Renda comprovada'), ['Documento válido', 'Renda comprovada']);
});
test('does not confuse approval and rejection terms', () => {
  assert.deepEqual(readingTerms('Indeferimento do pedido.'), [{ term: 'Indeferimento', meaning: 'Recusa de um pedido.' }]);
  assert.equal(readingTerms('Apoio à família.').length, 0);
});
