"""Testes do controle de fluxo, sem depender de Ollama ou banco local."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comparar as c


class AbstencaoTests(unittest.TestCase):
    def executar(self, decisoes, programas=None, resposta='Orientação fundamentada.'):
        decisao = {}
        with (patch.object(c, 'detectar_modelo', return_value='teste'),
              patch.object(c, 'decidir_json', side_effect=decisoes),
              patch.object(c, 'buscar_programas', return_value=programas or []) as busca,
              patch.object(c, 'montar_contextos', return_value=['doc1', 'doc2']),
              patch.object(c, 'chamar_ollama', return_value=(resposta, 0)) as gerar):
            resultado = c.responder_rag('pergunta', colecao=object(), decisao=decisao)
        return decisao, resultado, busca, gerar

    def test_fora_nao_busca_nem_gera(self):
        d, _, busca, gerar = self.executar([{'status': 'fora_do_escopo'}])
        self.assertTrue(d['absteve'])
        busca.assert_not_called()
        gerar.assert_not_called()

    def test_ambigua_pede_esclarecimento(self):
        d, r, busca, _ = self.executar([{'status': 'ambigua'}])
        self.assertIn('explicar', r[0])
        busca.assert_not_called()

    def test_sem_evidencia_nao_gera(self):
        d, _, _, gerar = self.executar([{'status': 'dentro'}, {'suficiente': False}], [1])
        self.assertEqual(d['status'], 'sem_evidencia')
        gerar.assert_not_called()

    def test_busca_vazia(self):
        d, _, _, gerar = self.executar([{'status': 'dentro'}])
        self.assertEqual(d['status'], 'sem_evidencia')
        gerar.assert_not_called()

    def test_classificacao_invalida(self):
        d, _, busca, _ = self.executar([{}])
        self.assertEqual(d['status'], 'falha_validacao')
        busca.assert_not_called()

    def test_documento_invalido(self):
        for indice in (0, 3, True, '1'):
            d, _, _, gerar = self.executar(
                [{'status': 'dentro'}, {'suficiente': True, 'documentos': [indice]}], [1, 2])
            self.assertEqual(d['status'], 'falha_validacao')
            gerar.assert_not_called()

    def test_usa_somente_documento_validado(self):
        d, _, _, gerar = self.executar(
            [{'status': 'dentro'}, {'suficiente': True, 'documentos': [2]}], [1, 2])
        self.assertFalse(d['absteve'])
        prompt = gerar.call_args.args[0][1]['content']
        self.assertIn('doc2', prompt)
        self.assertNotIn('doc1', prompt)

    def test_aviso_informativo_nao_e_recusa(self):
        self.assertFalse(c.verificar_abstencao('Este assistente é apenas informativo. Procure o CRAS.'))

    def test_recusa_do_gerador_padronizada(self):
        d, r, _, _ = self.executar(
            [{'status': 'dentro'}, {'suficiente': True, 'documentos': [1]}], [1],
            'Não há informações suficientes para responder.')
        self.assertEqual(d['status'], 'sem_evidencia')
        self.assertEqual(r[0], c.MENSAGENS_DECISAO['sem_evidencia'])


if __name__ == '__main__':
    unittest.main()
