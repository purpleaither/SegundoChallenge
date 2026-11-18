"""Orquestração do fluxo multiagente em LangGraph (5 nós sequenciais com Guardrail condicional)."""

from pathlib import Path
import sys

from dotenv import load_dotenv

# Garante que o diretório sistema_multiagente/ e seu .env sejam encontrados
# mesmo quando executado a partir da raiz do repositório.
PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))
load_dotenv(PASTA_ATUAL / ".env")

from langgraph.graph import END, START, StateGraph

from agents import (
    STATUS_ERRO_API,
    agente_analista_elegibilidade,
    agente_comunicador,
    agente_extrator_perfil,
    agente_guardrail,
    agente_retriever,
)
from schemas import EstadoSistema


def rotear_pos_guardrail(state: EstadoSistema) -> str:
    """Segue para extrator_perfil apenas se a mensagem estiver dentro do escopo e sem erro de API."""
    if state.get("dentro_do_escopo") and state.get("status_api") != STATUS_ERRO_API:
        return "extrator_perfil"
    return END


def _rotear_ou_encerrar(proximo_no: str):
    """Interrompe o fluxo imediatamente caso algum nó anterior tenha registrado erro de API."""
    def _roteador(state: EstadoSistema) -> str:
        if state.get("status_api") == STATUS_ERRO_API:
            return END
        return proximo_no

    return _roteador


def construir_grafo():
    workflow = StateGraph(EstadoSistema)

    # 1. Registro dos 5 nós/agentes especializados
    workflow.add_node("guardrail", agente_guardrail)
    workflow.add_node("extrator_perfil", agente_extrator_perfil)
    workflow.add_node("retriever", agente_retriever)
    workflow.add_node("analista_elegibilidade", agente_analista_elegibilidade)
    workflow.add_node("comunicador", agente_comunicador)

    # 2. Fluxo inicial e desvio condicional pós-Guardrail
    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges(
        "guardrail",
        rotear_pos_guardrail,
        {
            "extrator_perfil": "extrator_perfil",
            END: END,
        },
    )

    # 3. Sequência principal (com proteção contra falha de API intermediária)
    workflow.add_conditional_edges(
        "extrator_perfil",
        _rotear_ou_encerrar("retriever"),
        {"retriever": "retriever", END: END},
    )
    workflow.add_conditional_edges(
        "retriever",
        _rotear_ou_encerrar("analista_elegibilidade"),
        {"analista_elegibilidade": "analista_elegibilidade", END: END},
    )
    workflow.add_conditional_edges(
        "analista_elegibilidade",
        _rotear_ou_encerrar("comunicador"),
        {"comunicador": "comunicador", END: END},
    )
    workflow.add_edge("comunicador", END)

    return workflow.compile()


app = construir_grafo()


def estado_inicial(mensagem: str) -> EstadoSistema:
    return {
        "mensagem_usuario": mensagem.strip(),
        "dentro_do_escopo": False,
        "motivo_rejeicao": None,
        "perfil_extraido": None,
        "query_busca": None,
        "documentos_encontrados": None,
        "analise_elegibilidade": None,
        "resposta_final": "",
        "status_api": "iniciado",
    }


def executar_fluxo(mensagem: str) -> EstadoSistema:
    """Executa o pipeline completo de 5 agentes para a mensagem do usuário e retorna o EstadoSistema final."""
    return app.invoke(estado_inicial(mensagem))