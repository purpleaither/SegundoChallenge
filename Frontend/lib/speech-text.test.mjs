import assert from 'node:assert/strict';
import test from 'node:test';
import { speechText } from './speech-text.ts';
test('keeps values, conditions and support while removing Markdown and spoken URLs',()=>{
 const input='## Orientação\nVocê pode consultar **Bolsa Família** [1].\n\n**Próximos passos práticos**\n1. Confirme a renda de R$ 218,00 por pessoa no [órgão responsável](https://www.gov.br/).\n2. Acesse https://www.gov.br/servico para informações.\n\n### Apoio\nProcure atendimento presencial.';
 const result=speechText(input);for(const text of ['Bolsa Família','R$ 218,00 por pessoa','órgão responsável','Procure atendimento presencial.'])assert.ok(result.includes(text));
 for(const text of ['**','##','https://','[1]','1. Confirme'])assert.ok(!result.includes(text));
});
