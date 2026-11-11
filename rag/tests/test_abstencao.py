"""Controle de escopo e respostas fundamentadas, sem serviços externos."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comparar as c
import buscar


class AbstencaoTests(unittest.TestCase):
    def executar(self, status, programas=None):
        decisao = {}
        with (patch.object(c, 'detectar_modelo', return_value='teste'),
              patch.object(c, 'decidir_json', return_value={'status': status}),
              patch.object(c, 'buscar_programas', return_value=programas or []) as busca,
              patch.object(c, 'responder_com_fichas', return_value='Orientação fundamentada.') as render):
            resultado = c.responder_rag('pergunta', colecao=object(), decisao=decisao)
        return decisao, resultado, busca, render

    def test_fora_nao_busca(self):
        d, _, busca, render = self.executar('fora_do_escopo')
        self.assertTrue(d['absteve'])
        busca.assert_not_called()
        render.assert_not_called()

    def test_ambigua_pede_esclarecimento(self):
        _, r, busca, _ = self.executar('ambigua')
        self.assertIn('explicar', r[0])
        busca.assert_not_called()

    def test_busca_vazia(self):
        d, _, _, render = self.executar('dentro')
        self.assertEqual(d['status'], 'sem_evidencia')
        render.assert_not_called()

    def test_classificacao_invalida(self):
        d, _, busca, _ = self.executar('categoria_invalida')
        self.assertEqual(d['status'], 'falha_validacao')
        busca.assert_not_called()

    def test_sem_correspondencia_nao_inventa(self):
        d, _, _, render = self.executar('dentro', [{'relevancia_lexical': 0}])
        self.assertEqual(d['status'], 'sem_evidencia')
        render.assert_not_called()

    def test_documento_sem_relacao_e_excluido(self):
        relevante = {'meta': {'arquivo': 'a'}, 'relevancia_lexical': 10}
        d, _, _, render = self.executar('dentro', [relevante, {'relevancia_lexical': 1}])
        self.assertFalse(d['absteve'])
        self.assertEqual(render.call_args.args[0], [relevante])
        self.assertEqual(d['documentos_utilizados'], ['a'])

    def test_ficha_parcial_preservada(self):
        item = {'meta': {'arquivo': 'auxilio-gas-dos-brasileiros.md', 'orgao': 'MDS', 'fonte': 'base local'}}
        texto = c.responder_com_fichas([item])
        self.assertIn('Auxílio para compra de GLP', texto)
        self.assertIn('Informação parcial no documento', texto)
        self.assertIn('não garante a concessão', texto)
        self.assertNotIn('R$ 600', texto)

    def test_todas_as_fichas_renderizam(self):
        from ingestao import ler_documento
        for arquivo in c.PASTA_BASE.glob('*.md'):
            meta, _ = ler_documento(arquivo)
            with self.subTest(arquivo=arquivo.name):
                texto = c.responder_com_fichas([{'meta': dict(meta, arquivo=arquivo.name)}])
                self.assertIn('**Fonte:**', texto)
                self.assertIn('**Critérios:**', texto)

    def test_recupera_fies_e_alimentos_sem_vetor(self):
        with patch.object(buscar, 'buscar', return_value=[]):
            for pergunta, nome in [('financiamento faculdade FIES', 'FIES'), ('cesta comida fome', 'Alimentos')]:
                programas = buscar.buscar_programas(None, pergunta)
                self.assertTrue(any(nome in p['meta']['programa'] for p in programas))

    def test_dona_de_casa_nao_expande_moradia(self):
        self.assertNotIn('habitação', buscar.expandir('sou dona de casa, INSS mais barato'))

    def test_fonte_de_todos_os_campos_e_a_ficha(self):
        from ingestao import ler_documento
        for arquivo in c.PASTA_BASE.glob('*.md'):
            meta, _ = ler_documento(arquivo)
            f = c.ficha(arquivo.name)
            texto = c.responder_com_fichas([{'meta': dict(meta, arquivo=arquivo.name)}])
            for campo in ('Critérios', 'Público-alvo', 'Lei base', 'Regulamentação', 'Atualização recente', 'Observações'):
                self.assertIn(f[campo], texto)

    def test_bateria_recupera_programas_esperados_sem_vetor(self):
        from avaliar import DENTRO_DO_ESCOPO
        with patch.object(buscar, 'buscar', return_value=[]):
            for pergunta, esperado in DENTRO_DO_ESCOPO:
                with self.subTest(pergunta=pergunta):
                    programas = buscar.buscar_programas(None, pergunta)
                    melhor = max(p['relevancia_lexical'] for p in programas)
                    selecionados = [p for p in programas if p['relevancia_lexical'] >= melhor * .75]
                    self.assertTrue(any(esperado.casefold() in p['meta']['programa'].casefold() for p in selecionados))

    def test_limite_operacional_sem_numero_cpf(self):
        for pergunta in ('Consulte meu CadÚnico', 'faz meu cadastro', 'verifique se meu benefício foi aprovado'):
            self.assertTrue(c.violacao_operacional_p02(pergunta))
        for pergunta in ('Como faço meu cadastro no CadÚnico?', 'Onde consultar meu benefício?'):
            self.assertFalse(c.violacao_operacional_p02(pergunta))

    def test_aviso_nao_e_recusa(self):
        self.assertFalse(c.verificar_abstencao('Este assistente é apenas informativo. Procure o CRAS.'))


if __name__ == '__main__':
    unittest.main()
