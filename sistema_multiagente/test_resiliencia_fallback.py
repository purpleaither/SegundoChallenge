"""Testes unitários offline das 4 camadas de resiliência, fallback e degradação graciosa."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import httpx
from langchain_core.exceptions import (
    ModelAuthenticationError,
    ModelNotFoundError,
    ModelRateLimitError,
    ModelRefusalError,
    OutputParserException,
)

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))

if __package__:
    from . import agents
    from . import config
    from . import graph
    from . import llm_providers
    from . import main as cli_main
    from . import rag
    from .schemas import (
        STATUS_DEGRADADO,
        STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        STATUS_SUCESSO,
        AnaliseElegibilidade,
        AvaliacaoCriticaReflexion,
        AvaliacaoPrograma,
        PassoPlanoReWOO,
        PerfilSocioeconomico,
        PlanoReWOO,
        ValidacaoEscopo,
    )
else:
    import agents
    import config
    import graph
    import llm_providers
    import main as cli_main
    import rag
    from schemas import (
        STATUS_DEGRADADO,
        STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        STATUS_SUCESSO,
        AnaliseElegibilidade,
        AvaliacaoCriticaReflexion,
        AvaliacaoPrograma,
        PassoPlanoReWOO,
        PerfilSocioeconomico,
        PlanoReWOO,
        ValidacaoEscopo,
    )


class FakeStructuredLLM:
    """Stub leve de ChatGoogleGenerativeAI para testar invocar_estruturado/invocar_texto offline."""

    def __init__(self, handler_structured=None, handler_text=None) -> None:
        self._handler_structured = handler_structured
        self._handler_text = handler_text

    def with_structured_output(self, schema):
        class _Runner:
            def __init__(self, fn, sch) -> None:
                self._fn = fn
                self._sch = sch

            def invoke(self, mensagens):
                return self._fn(self._sch, mensagens)

        return _Runner(self._handler_structured, schema)

    def invoke(self, mensagens):
        return self._handler_text(mensagens)


class Camada1ConfigResilienciaTests(unittest.TestCase):
    def setUp(self) -> None:
        config.resetar_circuit_breaker()

    def tearDown(self) -> None:
        config.resetar_circuit_breaker()

    def test_lazy_init_sem_google_api_key_nao_falha_no_import_e_falha_em_obter_llm(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "LLM_FALLBACK_ORDER": ""}, clear=False):
            with self.assertRaises(ValueError):
                config.obter_llm("gemini-3.1-flash-lite")
            with self.assertRaises(ValueError):
                _ = config.llm
            with self.assertRaises(RuntimeError):
                config.invocar_texto("comunicador", "sys", "usr")

    def test_taxonomia_classifica_erros_tipados_http_e_mensagens_case_insensitive(self) -> None:
        self.assertEqual(
            config.classificar_erro_llm(ModelRateLimitError("429")),
            config.ERRO_TRANSITORIO,
        )
        self.assertEqual(
            config.classificar_erro_llm(ModelNotFoundError("not found")),
            config.ERRO_PERMANENTE_MODELO,
        )
        self.assertEqual(
            config.classificar_erro_llm(ModelAuthenticationError("invalid key")),
            config.ERRO_AUTENTICACAO_PROVEDOR,
        )
        self.assertEqual(
            config.classificar_erro_llm(ModelRefusalError("safety block")),
            config.ERRO_SEGURANCA_RECUSA,
        )
        self.assertEqual(
            config.classificar_erro_llm(OutputParserException("invalid json")),
            config.ERRO_PARSING_ESTRUTURADO,
        )
        self.assertEqual(
            config.classificar_erro_llm(httpx.ConnectError("Connection refused")),
            config.ERRO_TRANSITORIO,
        )
        self.assertEqual(
            config.classificar_erro_llm(httpx.ReadTimeout("request timeout")),
            config.ERRO_TRANSITORIO,
        )
        self.assertEqual(
            config.classificar_erro_llm(RuntimeError("503 currently experiencing high demand")),
            config.ERRO_TRANSITORIO,
        )
        self.assertEqual(
            config.classificar_erro_llm(RuntimeError("502 Bad Gateway")),
            config.ERRO_TRANSITORIO,
        )
        self.assertEqual(
            config.classificar_erro_llm(RuntimeError("500 Internal Server Error")),
            config.ERRO_TRANSITORIO,
        )

    def test_retry_tenacity_recupera_em_503_e_nao_retenta_404_ou_safety(self) -> None:
        chamadas: list[str] = []
        esperas: list[float] = []

        def _handler_text(nome_modelo: str):
            def _invoke(_msgs):
                chamadas.append(nome_modelo)
                if len(chamadas) == 1:
                    raise RuntimeError("503 UNAVAILABLE high demand")
                return MagicMock(text="Resposta recuperada após retry.", content="Resposta recuperada após retry.")

            return _invoke

        with (
            patch.dict(os.environ, {"GOOGLE_API_KEY": "chave-teste", "LLM_MAX_TENTATIVAS": "2", "LLM_FALLBACK_ORDER": ""}),
            patch.object(config, "_dormir", side_effect=esperas.append),
            patch.object(
                config,
                "obter_llm",
                side_effect=lambda nome, **kw: FakeStructuredLLM(handler_text=_handler_text(nome)),
            ),
        ):
            texto, modelo = config.invocar_texto("comunicador", "sys", "usr")

        self.assertEqual(texto, "Resposta recuperada após retry.")
        self.assertEqual(modelo, "gemini-3.5-flash-lite")
        self.assertEqual(chamadas, ["gemini-3.5-flash-lite", "gemini-3.5-flash-lite"])
        self.assertEqual(len(esperas), 1)

        # 404 não deve sofrer retry no mesmo modelo e deve cair direto para o próximo
        config.resetar_circuit_breaker()
        chamadas_404: list[str] = []
        esperas_404: list[float] = []

        def _handler_404(nome_modelo: str):
            def _invoke(_msgs):
                chamadas_404.append(nome_modelo)
                if nome_modelo == "gemini-3.5-flash-lite":
                    raise ModelNotFoundError("404 NOT_FOUND")
                return MagicMock(text="OK fallback", content="OK fallback")

            return _invoke

        with (
            patch.dict(os.environ, {"GOOGLE_API_KEY": "chave-teste", "LLM_MAX_TENTATIVAS": "3", "LLM_FALLBACK_ORDER": ""}),
            patch.object(config, "_dormir", side_effect=esperas_404.append),
            patch.object(
                config,
                "obter_llm",
                side_effect=lambda nome, **kw: FakeStructuredLLM(handler_text=_handler_404(nome)),
            ),
        ):
            texto2, modelo2 = config.invocar_texto("comunicador", "sys", "usr")

        self.assertEqual(texto2, "OK fallback")
        self.assertEqual(modelo2, "gemini-3.1-flash-lite")
        self.assertEqual(chamadas_404, ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"])
        self.assertEqual(esperas_404, [])

    def test_circuit_breaker_ttl_reabilita_429_mas_mantem_404_bloqueado(self) -> None:
        tempo = [100.0]

        def _now() -> float:
            return tempo[0]

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "chave-teste",
                    "LLM_MAX_TENTATIVAS": "1",
                    "LLM_COOLDOWN_SEGUNDOS": "60",
                    "LLM_FALLBACK_ORDER": "",
                },
            ),
            patch.object(config, "_relogio", side_effect=_now),
        ):
            # 1) 429 coloca modelo 1 em cooldown de 60s
            config._CIRCUIT_BREAKER.registrar_falha(
                "gemini-3.1-flash-lite", config.ERRO_TRANSITORIO, provedor="gemini", cooldown_base=60.0
            )
            # 2) 404 bloqueia modelo 2 permanentemente
            config._CIRCUIT_BREAKER.registrar_falha(
                "gemini-3.5-flash-lite", config.ERRO_PERMANENTE_MODELO, provedor="gemini"
            )

            disponiveis_durante, _, _ = config.cadeia_modelos_agente("guardrail")
            self.assertEqual(disponiveis_durante, ["gemini-4-hydrogen"])

            # Avança o relógio além do TTL (100 + 61 = 161s)
            tempo[0] = 161.0
            disponiveis_pos_ttl, _, _ = config.cadeia_modelos_agente("guardrail")
            self.assertEqual(disponiveis_pos_ttl, ["gemini-3.1-flash-lite", "gemini-4-hydrogen"])
            # Modelo 404 continua permanentemente excluído
            self.assertNotIn("gemini-3.5-flash-lite", disponiveis_pos_ttl)

    def test_autenticacao_401_abre_circuito_do_provedor_gemini_inteiro(self) -> None:
        chamadas_gemini: list[str] = []

        def _obter(nome: str, **kw):
            chamadas_gemini.append(nome)

            def _inv(_msgs):
                raise ModelAuthenticationError("401 API_KEY_INVALID")

            return FakeStructuredLLM(handler_text=_inv)

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "chave-invalida",
                    "LLM_MAX_TENTATIVAS": "2",
                    "LLM_FALLBACK_ORDER": "ollama",
                },
            ),
            patch.object(config, "obter_llm", side_effect=_obter),
            patch.object(
                llm_providers.ProvedorOllama,
                "invocar_texto",
                return_value=("Resposta via Ollama", "ollama/qwen2.5:7b"),
            ) as mock_ollama,
        ):
            texto, modelo = config.invocar_texto("comunicador", "sys", "usr")

        # Não deve tentar os outros 2 modelos Gemini após 401; salta imediatamente ao Ollama
        self.assertEqual(chamadas_gemini, ["gemini-3.5-flash-lite"])
        mock_ollama.assert_called_once()
        self.assertEqual(texto, "Resposta via Ollama")
        self.assertEqual(modelo, "ollama/qwen2.5:7b")
        self.assertEqual(config.cadeia_modelos_agente("guardrail")[0], [])

    def test_override_modelos_e_timeouts_por_env_e_sanitizacao_segredos(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEMINI_MODELO_RAPIDO": "gemini-custom-fast",
                "GEMINI_FALLBACKS_RAPIDO": "gemini-alt-1, gemini-alt-2",
                "LLM_TIMEOUT_RAPIDO": "25",
            },
        ):
            modelos, temp, timeout = config.cadeia_modelos_agente("guardrail")

        self.assertEqual(modelos, ["gemini-custom-fast", "gemini-alt-1", "gemini-alt-2"])
        self.assertEqual(temp, 0.0)
        self.assertEqual(timeout, 25)

        erro_sensivel = RuntimeError(
            "Falha POST https://api.example.com?key=AIzaSy1234567890ABCDEFGHIJKLMN "
            "Authorization: Bearer sk-secret1234567890123456"
        )
        sanitizado = config.sanitizar_mensagem_erro(erro_sensivel)
        self.assertNotIn("AIzaSy1234567890", sanitizado)
        self.assertNotIn("sk-secret1234567890", sanitizado)
        self.assertIn("[REDACTED", sanitizado)

    def test_extracao_texto_trata_blocos_e_lista_vazia(self) -> None:
        msg_blocos = MagicMock(text="", content=[{"type": "text", "text": "Linha 1"}, {"type": "text", "text": "Linha 2"}])
        self.assertEqual(llm_providers.extrair_texto_resposta(msg_blocos), "Linha 1\nLinha 2")

        msg_vazia = MagicMock(text="", content=[])
        self.assertEqual(llm_providers.extrair_texto_resposta(msg_vazia), "")


class Camada2ProvedoresSecundariosTests(unittest.TestCase):
    def setUp(self) -> None:
        config.resetar_circuit_breaker()

    def tearDown(self) -> None:
        config.resetar_circuit_breaker()

    def test_failover_para_ollama_estruturado_valida_todos_os_schemas_pydantic(self) -> None:
        casos = [
            (
                ValidacaoEscopo,
                {
                    "eh_valido": True,
                    "motivo": "Relato socioeconômico válido.",
                    "categoria_encaminhamento": None,
                    "tipo_bloqueio": None,
                    "padrao_execucao": "padrao",
                    "justificativa_padrao": "Relato direto.",
                },
            ),
            (
                PerfilSocioeconomico,
                {
                    "resumo_situacao": "Mãe solo desempregada.",
                    "situacao_trabalho": "desempregada",
                    "composicao_familiar": ["2 filhos"],
                    "condicoes_especificas": ["baixa renda"],
                    "palavras_chave_busca": ["Bolsa Família"],
                },
            ),
            (
                AnaliseElegibilidade,
                {
                    "programas_avaliados": [
                        {
                            "nome_programa": "Programa Bolsa Família",
                            "orgao_responsavel": "MDS",
                            "status_elegibilidade": "potencialmente_elegivel",
                            "criterios_atendidos": ["baixa renda"],
                            "criterios_pendentes_ou_impeditivos": ["inscrição no CadÚnico"],
                            "base_legal": "Lei nº 14.601/2023",
                            "observacoes_documentais": "Confirmar no CRAS.",
                        }
                    ],
                    "resumo_parecer": "Potencial acesso ao Bolsa Família.",
                },
            ),
            (
                PlanoReWOO,
                {
                    "perfil": {"resumo_situacao": "Relato multifacetado."},
                    "passos": [
                        {
                            "id_evidencia": "#E1",
                            "foco_necessidade": "transferência de renda",
                            "query_busca": "Bolsa Família baixa renda",
                        }
                    ],
                },
            ),
            (
                AvaliacaoCriticaReflexion,
                {
                    "aprovado": True,
                    "problemas_encontrados": [],
                    "instrucoes_correcao": "",
                },
            ),
        ]

        for schema, payload_json in casos:
            with self.subTest(schema=schema.__name__):
                config.resetar_circuit_breaker()
                resp_mock = MagicMock()
                resp_mock.raise_for_status.return_value = None
                resp_mock.json.return_value = {"message": {"content": json.dumps(payload_json, ensure_ascii=False)}}

                with (
                    patch.dict(
                        os.environ,
                        {
                            "GOOGLE_API_KEY": "",
                            "LLM_FALLBACK_ORDER": "ollama",
                            "OLLAMA_LLM_MODEL": "qwen2.5:7b",
                        },
                    ),
                    patch.object(httpx.Client, "post", return_value=resp_mock) as mock_post,
                ):
                    resultado, modelo = config.invocar_estruturado("guardrail", schema, "sys", "usr")

                self.assertIsInstance(resultado, schema)
                self.assertEqual(modelo, "ollama/qwen2.5:7b")
                enviado = mock_post.call_args.kwargs["json"]
                self.assertEqual(enviado["format"], schema.model_json_schema())
                self.assertFalse(enviado["stream"])
                self.assertEqual(enviado["options"]["num_ctx"], 8192)

    def test_ollama_texto_respeita_num_ctx_configuravel_e_minimo(self) -> None:
        resp_mock = MagicMock()
        resp_mock.raise_for_status.return_value = None
        resp_mock.json.return_value = {"message": {"content": "Orientação gerada via Ollama."}}

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "",
                    "LLM_FALLBACK_ORDER": "ollama",
                    "OLLAMA_LLM_MODEL": "qwen2.5:7b",
                    "OLLAMA_NUM_CTX": "12288",
                },
            ),
            patch.object(httpx.Client, "post", return_value=resp_mock) as mock_post,
        ):
            texto, modelo = config.invocar_texto("comunicador", "sys", "usr")

        self.assertEqual(texto, "Orientação gerada via Ollama.")
        self.assertEqual(modelo, "ollama/qwen2.5:7b")
        enviado = mock_post.call_args.kwargs["json"]
        self.assertEqual(enviado["options"]["num_ctx"], 12288)

    def test_ollama_offline_falha_rapido_sem_retry_e_preserva_erro_safety_do_gemini(self) -> None:
        esperas: list[float] = []

        def _gemini_safety(_schema, _msgs):
            raise ValueError("Saída estruturada vazia (finish_reason=SAFETY)")

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "chave-teste",
                    "LLM_MAX_TENTATIVAS": "3",
                    "LLM_FALLBACK_ORDER": "ollama",
                },
            ),
            patch.object(config, "_dormir", side_effect=esperas.append),
            patch.object(
                config,
                "obter_llm",
                side_effect=lambda nome, **kw: FakeStructuredLLM(handler_structured=_gemini_safety),
            ),
            patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Connection refused")) as mock_post,
        ):
            with self.assertRaises(ValueError) as ctx:
                config.invocar_estruturado("guardrail", ValidacaoEscopo, "sys", "usr")

        self.assertIn("SAFETY", str(ctx.exception))
        mock_post.assert_called_once()
        self.assertEqual(esperas, [])

    def test_openai_compatible_faz_fallback_de_json_schema_400_para_json_object(self) -> None:
        req = httpx.Request("POST", "https://api.exemplo.com/v1/chat/completions")
        resp_400 = httpx.Response(400, request=req, json={"error": "json_schema unsupported"})
        resp_200 = MagicMock()
        resp_200.raise_for_status.return_value = None
        resp_200.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "eh_valido": True,
                                "motivo": "Dúvida sobre Bolsa Família.",
                                "padrao_execucao": "padrao",
                                "justificativa_padrao": "Pergunta direta.",
                            }
                        )
                    }
                }
            ]
        }

        chamadas_payload: list[dict] = []

        def _fake_post(self_client, url, headers=None, json=None):
            chamadas_payload.append(json)
            if len(chamadas_payload) == 1:
                raise httpx.HTTPStatusError("400 Bad Request", request=req, response=resp_400)
            return resp_200

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "",
                    "LLM_FALLBACK_ORDER": "openai_compat",
                    "LLM_FALLBACK_BASE_URL": "https://api.exemplo.com/v1",
                    "LLM_FALLBACK_API_KEY": "sk-teste-unitario-1234567890",
                    "LLM_FALLBACK_MODEL": "llama-3.3-70b-versatile",
                },
            ),
            patch.object(httpx.Client, "post", new=_fake_post),
        ):
            resultado, modelo = config.invocar_estruturado("guardrail", ValidacaoEscopo, "sys", "usr")

        self.assertIsInstance(resultado, ValidacaoEscopo)
        self.assertEqual(modelo, "openai_compat/llama-3.3-70b-versatile")
        self.assertEqual(len(chamadas_payload), 2)
        self.assertEqual(chamadas_payload[0]["response_format"]["type"], "json_schema")
        self.assertEqual(chamadas_payload[1]["response_format"]["type"], "json_object")


class Camadas3e4DegradacaoPipelineTests(unittest.TestCase):
    def _doc_bolsa(self) -> list[str]:
        return [
            "=== DOCUMENTO 1 (similaridade: 0.88) ===\n"
            "Programa oficial: Bolsa Família\n"
            "Órgão responsável: Ministério do Desenvolvimento e Assistência Social, Família e Combate à Fome (MDS)\n"
            "URL oficial: https://www.gov.br/mds/pt-br/acoes-e-programas/bolsa-familia\n\n"
            "# Bolsa Família\n"
            "## Público e critérios\n"
            "Público-alvo: Famílias em situação de pobreza inscritas no CadÚnico.\n"
            "Critérios: Renda mensal por pessoa dentro do limite legal e inscrição no CadÚnico.\n"
            "Status dos critérios no documento: Completo\n"
            "## Legislação\n"
            "Legislação base: Lei nº 14.601/2023\n"
            "Regulamentação principal: Decreto nº 12.064/2024\n"
            "Atualização normativa recente: Portaria MDS 2025\n"
        ]

    def test_guardrail_simplifica_rewoo_para_padrao_quando_usando_ollama_local(self) -> None:
        validacao_rewoo = ValidacaoEscopo(
            eh_valido=True,
            motivo="Relato multifacetado.",
            padrao_execucao="rewoo",
            justificativa_padrao="Múltiplas vulnerabilidades.",
        )
        with patch.object(
            agents,
            "invocar_estruturado",
            return_value=(validacao_rewoo, "ollama/qwen2.5:7b"),
        ):
            out = agents.agente_guardrail(
                graph.estado_inicial("Moro na roça sem água, 2 filhos na escola e conta de luz alta")
            )

        self.assertTrue(out["dentro_do_escopo"])
        self.assertEqual(out["padrao_execucao"], "padrao")
        self.assertTrue(any("fallback local" in ev for ev in out["eventos_fallback"]))

    def test_reflexion_critico_falhando_preserva_resposta_do_comunicador_e_aviso_institucional(self) -> None:
        validacao = ValidacaoEscopo(
            eh_valido=True,
            motivo="Questão normativa sobre acumulação.",
            padrao_execucao="reflexion",
            justificativa_padrao="Caso limítrofe normativo.",
        )
        perfil = PerfilSocioeconomico(resumo_situacao="Dúvida sobre acumulação de BPC e Bolsa Família.")
        analise = AnaliseElegibilidade(
            programas_avaliados=[
                AvaliacaoPrograma(
                    nome_programa="Bolsa Família",
                    orgao_responsavel="MDS",
                    status_elegibilidade="potencialmente_elegivel",
                    criterios_atendidos=["baixa renda"],
                    criterios_pendentes_ou_impeditivos=["confirmar regra no CRAS"],
                    base_legal="Lei nº 14.601/2023",
                    observacoes_documentais="Confirmar acumulação no CRAS.",
                )
            ],
            resumo_parecer="Avaliar no CRAS.",
        )
        rascunho = (
            "Orientação completa validada sobre Bolsa Família e BPC.\n\n"
            "**Próximos passos práticos**\n1. Procure o CRAS."
        )

        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    (perfil, "gemini-3.1-flash-lite"),
                    (analise, "gemini-4-hydrogen"),
                    RuntimeError("429 RESOURCE_EXHAUSTED"),  # reflexion_critico falha
                ],
            ),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "BPC Bolsa Família", "documentos": self._doc_bolsa()},
            ),
            patch.object(agents, "invocar_texto", return_value=(rascunho, "gemini-3.5-flash-lite")),
        ):
            estado = graph.executar_fluxo("Posso acumular BPC com Bolsa Família?")

        self.assertEqual(estado["status_api"], STATUS_DEGRADADO)
        self.assertTrue(estado["modo_degradado"])
        self.assertIn("Orientação completa validada sobre Bolsa Família e BPC.", estado["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado["resposta_final"])
        self.assertEqual(estado["modelos_utilizados"]["reflexion_critico"], "ignorado_indisponibilidade_llm")
        self.assertTrue(estado["eventos_fallback"])

    def test_reflexion_revisor_falhando_preserva_resposta_anterior_validada(self) -> None:
        validacao = ValidacaoEscopo(
            eh_valido=True,
            motivo="Dúvida normativa.",
            padrao_execucao="reflexion",
            justificativa_padrao="Exige auditoria.",
        )
        perfil = PerfilSocioeconomico(resumo_situacao="Dúvida sobre Bolsa Família.")
        analise = AnaliseElegibilidade(programas_avaliados=[], resumo_parecer="Verificar no CRAS.")
        critica = AvaliacaoCriticaReflexion(
            aprovado=False,
            problemas_encontrados=["Faltou citar Decreto"],
            instrucoes_correcao="Incluir Decreto nº 12.064/2024.",
        )
        rascunho = "Resposta inicial acolhedora do comunicador.\n\n**Próximos passos práticos**\n1. Ir ao CRAS."

        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    (perfil, "gemini-3.1-flash-lite"),
                    (analise, "gemini-4-hydrogen"),
                    (critica, "gemini-4-hydrogen"),
                    RuntimeError("503 UNAVAILABLE"),  # reflexion_revisor falha na análise
                ],
            ),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "Bolsa Família", "documentos": self._doc_bolsa()},
            ),
            patch.object(agents, "invocar_texto", return_value=(rascunho, "gemini-3.5-flash-lite")),
        ):
            estado = graph.executar_fluxo("Quais leis regulam o Bolsa Família?")

        self.assertEqual(estado["status_api"], STATUS_DEGRADADO)
        self.assertIn("Resposta inicial acolhedora do comunicador.", estado["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado["resposta_final"])

    def test_rewoo_planner_falhando_faz_downgrade_para_padrao_e_conclui_com_sucesso(self) -> None:
        validacao = ValidacaoEscopo(
            eh_valido=True,
            motivo="Relato multifacetado.",
            padrao_execucao="rewoo",
            justificativa_padrao="Múltiplas frentes.",
        )
        perfil = PerfilSocioeconomico(resumo_situacao="Família rural com conta de luz alta.")
        analise = AnaliseElegibilidade(programas_avaliados=[], resumo_parecer="Programas identificados.")

        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    RuntimeError("503 UNAVAILABLE"),  # rewoo_planner falha -> downgrade para padrao
                    (perfil, "gemini-3.1-flash-lite"),  # extrator_perfil sucede
                    (analise, "gemini-4-hydrogen"),  # analista sucede
                ],
            ),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "rural luz", "documentos": self._doc_bolsa()},
            ) as mock_rag,
            patch.object(
                agents,
                "invocar_texto",
                return_value=("Orientação pelo fluxo padrão.\n\n**Próximos passos práticos**\n1. CRAS.", "gemini-3.5-flash-lite"),
            ),
        ):
            estado = graph.executar_fluxo("Moro na roça sem água, conta de luz alta e filhos na escola")

        mock_rag.assert_called_once()
        self.assertEqual(estado["status_api"], STATUS_SUCESSO)
        self.assertFalse(estado["modo_degradado"])
        self.assertEqual(estado["padrao_execucao"], "padrao")
        self.assertEqual(estado["modelos_utilizados"]["rewoo_planner"], "downgrade_para_padrao")
        self.assertIn("Orientação pelo fluxo padrão.", estado["resposta_final"])

    def test_rewoo_solver_preserva_analise_quando_comunicador_falha(self) -> None:
        validacao = ValidacaoEscopo(
            eh_valido=True,
            motivo="Relato multifacetado.",
            padrao_execucao="rewoo",
            justificativa_padrao="Múltiplas frentes.",
        )
        plano = PlanoReWOO(
            perfil=PerfilSocioeconomico(resumo_situacao="Desempregada com filhos."),
            passos=[PassoPlanoReWOO(id_evidencia="#E1", foco_necessidade="renda", query_busca="Bolsa Família")],
        )
        analise = AnaliseElegibilidade(
            programas_avaliados=[
                AvaliacaoPrograma(
                    nome_programa="Bolsa Família",
                    orgao_responsavel="MDS",
                    status_elegibilidade="potencialmente_elegivel",
                    criterios_atendidos=["baixa renda"],
                    criterios_pendentes_ou_impeditivos=["CadÚnico atualizado"],
                    base_legal="Lei nº 14.601/2023",
                    observacoes_documentais="Verificar no CRAS.",
                ),
                AvaliacaoPrograma(
                    nome_programa="Programa Inelegível Teste",
                    orgao_responsavel="Outro",
                    status_elegibilidade="inelegivel",
                    base_legal="Lei X",
                    observacoes_documentais="Não aplicável.",
                ),
            ],
            resumo_parecer="Potencial acesso ao Bolsa Família.",
        )

        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    (plano, "gemini-3.5-flash-lite"),
                    (analise, "gemini-4-hydrogen"),
                ],
            ),
            patch.object(
                agents,
                "executar_buscas_rewoo",
                return_value={
                    "query_busca": "#E1: Bolsa Família",
                    "evidencias_rewoo": {"#E1": self._doc_bolsa()},
                    "documentos": self._doc_bolsa(),
                },
            ),
            patch.object(agents, "invocar_texto", side_effect=RuntimeError("503 UNAVAILABLE")),
        ):
            estado = graph.executar_fluxo("Estou desempregada com 3 filhos, conta de luz e gás caros")

        self.assertEqual(estado["status_api"], STATUS_DEGRADADO)
        self.assertTrue(estado["modo_degradado"])
        self.assertIn("Bolsa Família", estado["resposta_final"])
        self.assertNotIn("Programa Inelegível Teste", estado["resposta_final"])
        self.assertIn("Lei nº 14.601/2023", estado["resposta_final"])
        self.assertIn("**Próximos passos práticos**", estado["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado["resposta_final"])

    def test_analista_e_comunicador_falhando_no_padrao_preservam_documentos_e_analise(self) -> None:
        validacao = ValidacaoEscopo(
            eh_valido=True,
            motivo="Dúvida direta.",
            padrao_execucao="padrao",
            justificativa_padrao="Fluxo simples.",
        )
        perfil = PerfilSocioeconomico(resumo_situacao="Desempregada com 2 filhos.")

        # 1) Falha no analista_elegibilidade -> renderiza fichas oficiais recuperadas sem afirmar elegibilidade
        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    (perfil, "gemini-3.1-flash-lite"),
                    RuntimeError("503 UNAVAILABLE"),
                ],
            ),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "Bolsa Família", "documentos": self._doc_bolsa()},
            ),
        ):
            estado_analista = graph.executar_fluxo("Estou desempregada com 2 filhos")

        self.assertEqual(estado_analista["status_api"], STATUS_DEGRADADO)
        self.assertIn("sem afirmação de direito ou elegibilidade", estado_analista["resposta_final"])
        self.assertIn("Bolsa Família", estado_analista["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado_analista["resposta_final"])

        # 2) Falha apenas no comunicador -> preserva parecer da analise_elegibilidade
        analise = AnaliseElegibilidade(
            programas_avaliados=[
                AvaliacaoPrograma(
                    nome_programa="Bolsa Família",
                    orgao_responsavel="MDS",
                    status_elegibilidade="potencialmente_elegivel",
                    criterios_atendidos=["baixa renda"],
                    criterios_pendentes_ou_impeditivos=["confirmar CadÚnico"],
                    base_legal="Lei nº 14.601/2023",
                    observacoes_documentais="Confirmar no CRAS.",
                )
            ],
            resumo_parecer="Potencial acesso ao Bolsa Família.",
        )
        with (
            patch.object(
                agents,
                "invocar_estruturado",
                side_effect=[
                    (validacao, "gemini-3.1-flash-lite"),
                    (perfil, "gemini-3.1-flash-lite"),
                    (analise, "gemini-4-hydrogen"),
                ],
            ),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "Bolsa Família", "documentos": self._doc_bolsa()},
            ),
            patch.object(agents, "invocar_texto", side_effect=RuntimeError("503 UNAVAILABLE")),
        ):
            estado_com = graph.executar_fluxo("Estou desempregada com 2 filhos")

        self.assertEqual(estado_com["status_api"], STATUS_DEGRADADO)
        self.assertIn("resumo da análise já realizada", estado_com["resposta_final"])
        self.assertIn("confirmar CadÚnico", estado_com["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado_com["resposta_final"])

    def test_fallback_rag_sem_documentos_retorna_orientacao_honesta_ao_cras(self) -> None:
        texto = rag.compor_resposta_deterministica_rag(
            documentos=[],
            analise_elegibilidade=None,
            aviso_institucional=agents.AVISO_INSTITUCIONAL,
        )
        self.assertIn("não encontrei fichas suficientemente próximas", texto)
        self.assertIn("**Próximos passos práticos**", texto)
        self.assertIn(agents.AVISO_INSTITUCIONAL, texto)

    def test_queda_total_llm_no_guardrail_entrega_rag_deterministico_para_relato_valido(self) -> None:
        with (
            patch.object(agents, "invocar_estruturado", side_effect=RuntimeError("503 UNAVAILABLE")),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": "desempregada filhos", "documentos": self._doc_bolsa()},
            ) as mock_rag,
        ):
            estado = graph.executar_fluxo("Estou desempregada com 3 filhos pequenos e sem renda")

        mock_rag.assert_called_once()
        self.assertEqual(estado["status_api"], STATUS_DEGRADADO)
        self.assertTrue(estado["modo_degradado"])
        self.assertIn("modo informativo simplificado", estado["resposta_final"])
        self.assertIn("Bolsa Família", estado["resposta_final"])
        self.assertIn("Lei nº 14.601/2023", estado["resposta_final"])
        self.assertIn("**Próximos passos práticos**", estado["resposta_final"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado["resposta_final"])

    def test_queda_total_llm_protege_indicio_sensivel_em_503_e_mantem_resposta_dupla(self) -> None:
        frase = "Sofri agressão ontem, estou desempregada com 2 filhos e preciso de auxílio"
        with (
            patch.object(agents, "invocar_estruturado", side_effect=RuntimeError("503 UNAVAILABLE")),
            patch.object(
                agents,
                "recuperar_documentos_com_perfil",
                return_value={"query_busca": frase, "documentos": self._doc_bolsa()},
            ),
        ):
            estado = graph.executar_fluxo(frase)

        self.assertEqual(estado["status_api"], STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA)
        self.assertEqual(estado["categoria_encaminhamento"], "codigo_penal")
        self.assertIn("Bolsa Família", estado["resposta_beneficios"])
        self.assertIn(agents.AVISO_INSTITUCIONAL, estado["resposta_beneficios"])
        self.assertIn("190", estado["mensagem_apoio"])
        self.assertIn("180", estado["mensagem_apoio"])
        self.assertIn("129", estado["mensagem_apoio"])

    def test_queda_total_llm_bloqueia_fora_de_escopo_e_indicio_de_fraude(self) -> None:
        with (
            patch.object(agents, "invocar_estruturado", side_effect=RuntimeError("503 UNAVAILABLE")),
            patch.object(agents, "recuperar_documentos_com_perfil") as mock_rag,
        ):
            estado_fora = graph.executar_fluxo("Me passa uma receita de bolo de cenoura")
            estado_fraude = graph.executar_fluxo("Posso omitir renda para receber o Bolsa Família?")

        mock_rag.assert_not_called()
        self.assertEqual(estado_fora["status_api"], STATUS_ERRO_API)
        self.assertFalse(estado_fora["dentro_do_escopo"])

        self.assertEqual(estado_fraude["status_api"], STATUS_ENCAMINHAMENTO_AJUDA)
        self.assertEqual(estado_fraude["categoria_encaminhamento"], "codigo_penal")
        self.assertIsNone(estado_fraude["resposta_beneficios"])
        self.assertIn("jamais pode apoiar ou orientar práticas ilícitas", estado_fraude["resposta_final"])

    def test_cli_debug_exibe_modo_degradado_e_eventos_de_fallback(self) -> None:
        estado_deg = {
            **graph.estado_inicial("Estou desempregada com 2 filhos"),
            "dentro_do_escopo": True,
            "padrao_execucao": "padrao",
            "categoria_encaminhamento": "autoexterminio",
            "modo_degradado": True,
            "eventos_fallback": ["guardrail: indisponibilidade LLM; ativado fallback determinístico RAG"],
            "modelos_utilizados": {
                "guardrail": "fallback_deterministico_seguranca",
                "retriever": "chromadb_local",
                "fallback_rag": "deterministico_rag_oficial",
            },
            "resposta_beneficios": "Fichas oficiais.",
            "mensagem_apoio": agents.MENSAGEM_AJUDA_AUTOEXTERMINIO,
            "resposta_final": f"Fichas oficiais.{agents.SEPARADOR_MENSAGEM_APOIO}{agents.MENSAGEM_AJUDA_AUTOEXTERMINIO}",
            "status_api": STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA,
        }

        buf = io.StringIO()
        with redirect_stdout(buf):
            cli_main.exibir_debug(estado_deg)
        saida = buf.getvalue()
        self.assertIn("PADRAO + MODO DEGRADADO + ENCAMINHAMENTO DE AJUDA", saida)
        self.assertIn("[EVENTOS DE FALLBACK / RESILIÊNCIA]", saida)
        self.assertIn("guardrail: indisponibilidade LLM", saida)


if __name__ == "__main__":
    unittest.main()
