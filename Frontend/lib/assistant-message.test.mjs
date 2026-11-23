import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require=createRequire(import.meta.url),ts=require('typescript');
for(const extension of ['.tsx','.ts'])require.extensions[extension]=(module,filename)=>module._compile(ts.transpileModule(readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText,filename);
const Module=require('node:module'),resolve=Module._resolveFilename;
Module._resolveFilename=function(name,...args){if(name==='@/lib/readable-text')name=new URL('./readable-text.ts',import.meta.url).pathname;return resolve.call(this,name,...args);};
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const Message=require('../app/components/assistant-message.tsx').default;
test('shows the API answer outside disclosures, with ordered official sources',()=>{
 const text='Bolsa Família [1]. A informação sobre os critérios é parcial; confirme na fonte oficial.';
 const programa={programa:'bolsa',titulo:'Bolsa Família',esfera:'Federal',orgao:'MDS',resumo:'Transferência de renda.',publico_alvo:'Famílias.',criterios:'Cadastro atualizado.',lei:'Lei nº 14.601/2023',url:'https://www.gov.br/fonte'};
 const html=renderToStaticMarkup(React.createElement(Message,{text,programas:[programa],notice:'Orientação informativa.'}));
 const firstDetails=html.indexOf('<details');assert.ok(html.indexOf('A informação sobre os critérios é parcial; confirme na fonte oficial.')<firstDetails);
 assert.ok(html.includes('aria-label="Fontes oficiais consultadas"'));assert.ok(html.includes('https://www.gov.br/fonte'));assert.ok(html.includes('Ver detalhes dos programas'));assert.ok(html.includes('Orientação informativa.'));
 assert.ok(!html.includes('Encontrei 4 programas'));
});
test('shows abstention text with no fabricated cards or citations',()=>{
 const html=renderToStaticMarkup(React.createElement(Message,{text:'Não encontrei contexto suficiente.',programas:[]}));assert.ok(html.includes('Não encontrei contexto suficiente.'));assert.ok(!html.includes('<details'));assert.ok(!html.includes('<ol'));
});
test('renders natural-language Markdown and separate support without executable HTML',()=>{
 const html=renderToStaticMarkup(React.createElement(Message,{text:'## Orientação\nVocê pode consultar **Bolsa Família**.\n\n**Próximos passos práticos**\n1. Vá ao órgão responsável.\n\n<script>alert(1)</script>\n\n[link](javascript:alert(1))',support:'**Apoio adicional**\nProcure atendimento presencial.'}));
 assert.ok(html.includes('<strong>Bolsa Família</strong>'));assert.ok(html.includes('<h2>Orientação</h2>'));assert.ok(html.includes('<ol>'));assert.ok(html.includes('aria-label="Orientação adicional de apoio"'));
 assert.equal((html.match(/Procure atendimento presencial\./g)||[]).length,1);assert.ok(!html.includes('<script'));assert.ok(!html.includes('href="javascript:'));
});
