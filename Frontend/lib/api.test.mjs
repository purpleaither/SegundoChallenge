import assert from 'node:assert/strict';
import test from 'node:test';
import { perguntar, adaptAssistantResponse } from './api.ts';
const benefit={id:'bolsa-familia',name:'Bolsa Família',current_name:'',agency_id:'MDS',scope:'Federal',category:'Renda',summary:'Transferência de renda.',benefit_type:'Transferência monetária',audience:'Famílias.',criteria:['Condição A.','Condição B.'],legislation_base:'Lei nº 14.601/2023',legislation_url:'https://www.planalto.gov.br/lei',source_url:'https://www.gov.br/fonte'};
const fixture={answer:'Bolsa Família [1]. Informação parcial; confirme no órgão responsável.',benefits:[benefit],notice:'Informação sem confirmação de elegibilidade.',status:'sucesso',speech_text:'Bolsa Família [1]. Informação parcial; confirme no órgão responsável.',support_message:null,execution_pattern:'padrao'};
test('calls the current endpoint using its contract and preserves exact answer',async()=>{
 const abort=new AbortController();
 const result=await perguntar('Mãe solo',abort.signal,async(url,options)=>{
  assert.equal(url,'/api/orientar');assert.deepEqual(JSON.parse(options.body),{question:'Mãe solo'});assert.equal(options.signal,abort.signal);
  return Response.json(fixture);
 });
 assert.equal(result.resposta,fixture.answer);assert.equal(result.aviso,fixture.notice);assert.equal(result.programas[0].criterios,'Condição A. Condição B.');assert.equal(result.programas[0].url,benefit.legislation_url);assert.equal(result.programas[0].lei,benefit.legislation_base);
 assert.equal('similaridade' in result.programas[0],false);
});
test('preserves abstention and errors instead of inventing an answer',async()=>{
 const result=adaptAssistantResponse({answer:'Sem informação suficiente.',benefits:[],notice:'Sem fontes.',status:'bloqueado_guardrail',speech_text:'Sem informação suficiente.',support_message:null,execution_pattern:null});assert.equal(result.fora_do_escopo,true);assert.deepEqual(result.programas,[]);
 await assert.rejects(perguntar('Pergunta',undefined,async()=>Response.json({detail:'Busca indisponível.'},{status:503})),/Busca indisponível/);
 assert.throws(()=>adaptAssistantResponse({resposta:'Contrato antigo'}),/inválida/);
});
test('preserves benefit guidance, separate support and speech without silent fallback',async()=>{
 const combined={...fixture,support_message:'Procure apoio presencial.',speech_text:fixture.answer+'\n\nProcure apoio presencial.',status:'sucesso_com_encaminhamento_ajuda',execution_pattern:'reflexion'};
 const result=adaptAssistantResponse(combined);assert.equal(result.apoio,'Procure apoio presencial.');assert.equal(result.fala,combined.speech_text);assert.equal(result.padrao,'reflexion');assert.equal(result.resposta,fixture.answer);
 let calls=0;await assert.rejects(perguntar('Pergunta',undefined,async(url)=>{calls++;assert.equal(url,'/api/orientar');return Response.json({detail:'Configuração pendente.'},{status:503});}),/Configuração pendente/);assert.equal(calls,1);
});
