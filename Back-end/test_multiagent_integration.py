import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
import multiagent_service as service

# Dummy credentials instantiate clients only; every model invocation is replaced below.
with patch.dict(os.environ, {'GOOGLE_API_KEY': 'teste-unitario-sem-rede'}):
    from sistema_multiagente import agents, graph
    from sistema_multiagente.schemas import (
        ValidacaoEscopo, PerfilSocioeconomico, AnaliseElegibilidade,
        AvaliacaoPrograma, PlanoReWOO, PassoPlanoReWOO, AvaliacaoCriticaReflexion,
    )


class HttpPipelineTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.benefit = next(b for b in main.load_programs() if b.name == 'Bolsa Família')
        self.docs = ['=== DOCUMENTO 1 ===\nPrograma oficial: Bolsa Família\nÓrgão responsável: MDS\nDocumento de teste.']
        self.profile = PerfilSocioeconomico(resumo_situacao='Família com dúvida sobre renda.')
        self.analysis = AnaliseElegibilidade(resumo_parecer='Confirme os critérios no órgão responsável.', programas_avaliados=[
            AvaliacaoPrograma(nome_programa='Bolsa Família', orgao_responsavel='MDS', status_elegibilidade='criterio_nao_especificado_na_base', base_legal='Lei nº 14.601/2023', observacoes_documentais='Critérios parciais.')
        ])
    def tearDown(self):
        self.client.close()
    def state(self, **updates):
        value = {'status_api':'sucesso','dentro_do_escopo':True,'padrao_execucao':'padrao', 'resposta_final':'**Bolsa Família**. Confirme no órgão responsável.', 'resposta_beneficios':'**Bolsa Família**. Confirme no órgão responsável.','mensagem_apoio':None,'documentos_encontrados':self.docs,'analise_elegibilidade':self.analysis.model_dump()}
        return {**value, **updates}
    def post(self):
        return self.client.post('/api/orientar', json={'question':'Quero orientação sobre renda familiar.'})
    def test_http_preserves_guidance_and_support_without_internal_profile(self):
        state=self.state(status_api='sucesso_com_encaminhamento_ajuda', mensagem_apoio='Procure apoio presencial.', resposta_final='Orientação.\n\nProcure apoio presencial.', perfil_extraido={'renda':'não exibir'})
        with patch.object(main,'execute_pipeline',return_value=state): response=self.post()
        self.assertEqual(response.status_code,200)
        result=response.json()
        self.assertEqual(result['support_message'],'Procure apoio presencial.')
        self.assertNotIn('Procure apoio presencial.',result['answer'])
        self.assertEqual(result['speech_text'],state['resposta_final'])
        self.assertEqual(result['benefits'][0]['id'],self.benefit.id)
        self.assertEqual(result['sources'][0]['id'],self.benefit.id)
        self.assertNotIn('perfil_extraido',result)
    def test_does_not_offer_ineligible_or_unretrieved_programs(self):
        state=self.state()
        state['analise_elegibilidade']['programas_avaliados'][0]['status_elegibilidade']='inelegivel'
        self.assertEqual(service.response_from_state(state,[self.benefit])['benefits'],[])
        self.assertEqual(service.response_from_state(self.state(documentos_encontrados=[]),[self.benefit])['benefits'],[])
    def test_support_survives_provider_error_and_is_not_duplicated(self):
        state=self.state(status_api='erro_api',resposta_beneficios=None,mensagem_apoio='Procure apoio presencial.',resposta_final='Falha técnica.\n\nProcure apoio presencial.')
        with patch.object(main,'execute_pipeline',return_value=state): result=self.post().json()
        self.assertEqual(result['status'],'erro_api')
        self.assertEqual(result['answer'],'Falha técnica.')
        self.assertEqual(result['support_message'],'Procure apoio presencial.')
        self.assertEqual(result['benefits'],[])
    def test_support_only_and_guardrail_refusal(self):
        for state in [self.state(status_api='encaminhamento_ajuda',resposta_beneficios=None,mensagem_apoio='Procure apoio presencial.',resposta_final='Procure apoio presencial.'), self.state(status_api='bloqueado_guardrail',resposta_beneficios=None,resposta_final='Não realizo consultas de cadastro.')]:
            with patch.object(main,'execute_pipeline',return_value=state): response=self.post()
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['benefits'],[])
        support=service.response_from_state(self.state(status_api='encaminhamento_ajuda',resposta_beneficios=None,mensagem_apoio='Apoio.',resposta_final='Apoio.'),[])
        self.assertEqual(support['answer'],'')
    def test_unavailable_busy_and_empty_input_have_explicit_errors(self):
        for error,status in [(service.PipelineUnavailable('Configuração pendente.'),503),(service.PipelineBusy(),429)]:
            with patch.object(main,'execute_pipeline',side_effect=error): self.assertEqual(self.post().status_code,status)
        self.assertEqual(self.client.post('/api/orientar',json={'question':'   '}).status_code,422)
        with patch.object(main,'run_in_threadpool',side_effect=TimeoutError): self.assertEqual(self.post().status_code,504)
        with patch.object(service,'configured',return_value=False):
            with self.assertRaises(service.PipelineUnavailable): service.execute_pipeline('Pergunta')
    def test_all_three_graph_routes_reach_the_http_response(self):
        for pattern in ['padrao','rewoo','reflexion']:
            calls=[]
            validation=ValidacaoEscopo(eh_valido=True,motivo='Consulta de benefício.',padrao_execucao=pattern,justificativa_padrao='Teste de roteamento.')
            def structured(agent,schema,*args):
                calls.append(agent)
                values={
                    'guardrail':validation,'extrator_perfil':self.profile,'analista_elegibilidade':self.analysis,
                    'rewoo_planner':PlanoReWOO(perfil=self.profile,passos=[PassoPlanoReWOO(id_evidencia='#E1',foco_necessidade='Renda',query_busca='Bolsa Família')]),
                    'rewoo_solver':self.analysis,
                    'reflexion_critico':AvaliacaoCriticaReflexion(aprovado=True),
                }
                return values[agent],'modelo-simulado'
            def text(agent,*args):
                calls.append(agent)
                return '**Bolsa Família**\n\n**Próximos passos práticos**\n1. Confirme os critérios no órgão responsável.','modelo-simulado'
            with (
                patch.object(agents,'invocar_estruturado',side_effect=structured),
                patch.object(agents,'invocar_texto',side_effect=text),
                patch.object(agents,'recuperar_documentos_com_perfil',return_value={'query_busca':'Renda','documentos':self.docs}),
                patch.object(agents,'executar_buscas_rewoo',return_value={'query_busca':'Renda','documentos':self.docs,'evidencias_rewoo':{'#E1':self.docs}}),
                patch.object(main,'execute_pipeline',side_effect=graph.executar_fluxo),
            ):
                response=self.post()
            with self.subTest(pattern=pattern):
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['execution_pattern'],pattern)
                self.assertEqual(response.json()['status'],'sucesso')
                self.assertIn('Próximos passos práticos',response.json()['answer'])
                self.assertEqual(response.json()['benefits'][0]['id'],self.benefit.id)
                if pattern=='reflexion':self.assertIn('reflexion_critico',calls)
                if pattern=='rewoo':self.assertIn('rewoo_planner',calls)

    def test_degraded_statuses_return_http_200_and_preserve_support_and_sources(self):
        state = self.state(
            status_api='sucesso_degradado_com_encaminhamento_ajuda',
            analise_elegibilidade=None,
            mensagem_apoio='Procure apoio presencial.',
            resposta_beneficios='**Aviso de modo informativo simplificado:** fichas oficiais.',
            resposta_final='**Aviso de modo informativo simplificado:** fichas oficiais.\n\nProcure apoio presencial.',
        )
        with patch.object(main, 'execute_pipeline', return_value=state):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'sucesso_degradado_com_encaminhamento_ajuda')
        self.assertEqual(body['support_message'], 'Procure apoio presencial.')
        self.assertEqual(body['sources'][0]['id'], self.benefit.id)
        self.assertEqual(body['benefits'], [])


if __name__=='__main__': unittest.main()
