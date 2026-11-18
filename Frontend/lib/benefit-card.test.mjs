import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const ts = require('typescript');
// Compile this isolated React component using the project's existing compiler.
for (const extension of ['.tsx', '.ts']) {
  require.extensions[extension] = (module, filename) => {
    module._compile(ts.transpileModule(readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 }
    }).outputText, filename);
  };
}
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
// Resolve the sole runtime alias in reading-topics without adding a dependency.
const Module = require('node:module');
const resolve = Module._resolveFilename;
Module._resolveFilename = function(request, ...args) {
  if (request === '@/lib/readable-text') request = new URL('./readable-text.ts', import.meta.url).pathname;
  return resolve.call(this, request, ...args);
};
const Card = require('../app/components/benefit-card.tsx').default;
const fixture = {
  programa: 'exemplo', titulo: 'Programa de teste', esfera: 'Federal', orgao: 'Órgão de teste',
  resumo: 'Ajuda em dinheiro. Não há aprovação automática.',
  publico_alvo: 'Famílias com cadastro.', criterios: 'Renda per capita de até R$ 1.518,00; e cadastro atualizado.',
  lei: 'Lei nº 14.601/2023', url: 'https://www.gov.br/', categoria: 'Teste', similaridade: 0.8
};

test('renders readable sections, original conditions and official reference', () => {
  const html = renderToStaticMarkup(React.createElement(Card, { programa: fixture }));
  for (const text of ['O que é', 'Para quem é', 'Quem pode pedir', 'Entenda os termos', 'Descrição original', 'Critérios originais', fixture.criterios, fixture.lei]) assert.ok(html.includes(text), text);
  assert.match(html, /<li>Ajuda em dinheiro\.<\/li>/);
  assert.match(html, /<li>Não há aprovação automática\.<\/li>/);
  assert.match(html, /href="https:\/\/www.gov.br\/"/);
});
test('does not invent eligibility criteria when the base is incomplete', () => {
  const html = renderToStaticMarkup(React.createElement(Card, { programa: { ...fixture, criterios: 'Não especificado na base', lei: null, url: null } }));
  assert.ok(html.includes('A base não informa os critérios.'));
  assert.ok(html.includes('Não especificado na base'));
  assert.ok(!html.includes('Consultar fonte oficial'));
});
