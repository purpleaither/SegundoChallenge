"""Orquestração multiagente em LangGraph com roteamento dinâmico entre Padrão, ReWOO e Reflexion."""

from pathlib import Path
import sys

from dotenv import load_dotenv

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))
load_dotenv(PASTA_ATUAL / ".env")

from langgraph.graph import END, START, StateGraph

from .agents import (
    MAX_ITERACOES_REFLEXION,
    STATUS_BLOQUEADO,
    STATUS_ENCAMINHAMENTO_AJUDA,
    STATUS_ERRO_API,
    agente_analista_elegibilidade,
    agente_comunicador,
    agente_extrator_perfil,
    agente_guardrail,
    agente_reflexion_critico,
    agente_reflexion_revisor,
    agente_retriever,
    agente_rewoo_planner,
    agente_rewoo_solver,
    agente_rewoo_worker,
    consolidar_encaminhamento_ajuda,
)
from .schemas import STATUS_INICIADO, EstadoSistema


def rotear_pos_guardrail(state: EstadoSistema) -> str:
    """Encerra se não houver escopo de benefícios ou erro; caso válido, desvia entre ReWOO e pipeline base."""
    if (
        not state.get("dentro_do_escopo")
        or state.get("status_api") in (STATUS_ERRO_API, STATUS_BLOQUEADO, STATUS_ENCAMINHAMENTO_AJUDA)
    ):
        return END
    if state.get("padrao_execucao") == "rewoo":
        return "rewoo_planner"
    return "extrator_perfil"


def _rotear_ou_encerrar(proximo_no: str):
    """Em erro de API, desvia para o consolidador final (preservando mensagem_apoio se houver)."""
    def _roteador(state: EstadoSistema) -> str:
        if state.get("status_api") == STATUS_ERRO_API:
            return "consolidar_encaminhamento_ajuda"
        return proximo_no

    return _roteador


def rotear_pos_comunicador(state: EstadoSistema) -> str:
    """No padrão 'padrao' consolida saída; no padrão 'reflexion' encaminha para auditoria do Crítico."""
    if state.get("status_api") == STATUS_ERRO_API:
        return "consolidar_encaminhamento_ajuda"
    if state.get("padrao_execucao") == "reflexion":
        return "reflexion_critico"
    return "consolidar_encaminhamento_ajuda"


def rotear_pos_critico(state: EstadoSistema) -> str:
    """Consolida saída se aprovado pelo Crítico, erro de API ou limite atingido; senão revisa."""
    if state.get("status_api") == STATUS_ERRO_API:
        return "consolidar_encaminhamento_ajuda"
    critica = state.get("critica_reflexion") or {}
    iteracao = int(state.get("iteracao_reflexion") or 0)
    if critica.get("aprovado") is True or iteracao >= MAX_ITERACOES_REFLEXION:
        return "consolidar_encaminhamento_ajuda"
    return "reflexion_revisor"


def construir_grafo():
    workflow = StateGraph(EstadoSistema)

    # 1. Registro dos nós (Guardrail/Seletor + Padrão + ReWOO + Reflexion + Consolidador de Apoio)
    workflow.add_node("guardrail", agente_guardrail)
    workflow.add_node("extrator_perfil", agente_extrator_perfil)
    workflow.add_node("retriever", agente_retriever)
    workflow.add_node("analista_elegibilidade", agente_analista_elegibilidade)
    workflow.add_node("comunicador", agente_comunicador)

    workflow.add_node("rewoo_planner", agente_rewoo_planner)
    workflow.add_node("rewoo_worker", agente_rewoo_worker)
    workflow.add_node("rewoo_solver", agente_rewoo_solver)

    workflow.add_node("reflexion_critico", agente_reflexion_critico)
    workflow.add_node("reflexion_revisor", agente_reflexion_revisor)
    workflow.add_node("consolidar_encaminhamento_ajuda", consolidar_encaminhamento_ajuda)

    # 2. Entrada e roteamento dinâmico pós-Guardrail
    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges(
        "guardrail",
        rotear_pos_guardrail,
        {
            "extrator_perfil": "extrator_perfil",
            "rewoo_planner": "rewoo_planner",
            END: END,
        },
    )

    # 3. Caminho Padrão + Base do Reflexion
    workflow.add_conditional_edges(
        "extrator_perfil",
        _rotear_ou_encerrar("retriever"),
        {"retriever": "retriever", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_conditional_edges(
        "retriever",
        _rotear_ou_encerrar("analista_elegibilidade"),
        {
            "analista_elegibilidade": "analista_elegibilidade",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_conditional_edges(
        "analista_elegibilidade",
        _rotear_ou_encerrar("comunicador"),
        {"comunicador": "comunicador", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_conditional_edges(
        "comunicador",
        rotear_pos_comunicador,
        {
            "reflexion_critico": "reflexion_critico",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )

    # 4. Ciclo Reflexion (Crítico <-> Revisor com limite MAX_ITERACOES_REFLEXION)
    workflow.add_conditional_edges(
        "reflexion_critico",
        rotear_pos_critico,
        {
            "reflexion_revisor": "reflexion_revisor",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_conditional_edges(
        "reflexion_revisor",
        _rotear_ou_encerrar("reflexion_critico"),
        {"reflexion_critico": "reflexion_critico", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )

    # 5. Caminho ReWOO (Planner -> Worker -> Solver -> Consolidador -> END)
    workflow.add_conditional_edges(
        "rewoo_planner",
        _rotear_ou_encerrar("rewoo_worker"),
        {"rewoo_worker": "rewoo_worker", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_conditional_edges(
        "rewoo_worker",
        _rotear_ou_encerrar("rewoo_solver"),
        {"rewoo_solver": "rewoo_solver", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_edge("rewoo_solver", "consolidar_encaminhamento_ajuda")
    workflow.add_edge("consolidar_encaminhamento_ajuda", END)

    return workflow.compile()


app = construir_grafo()


def estado_inicial(mensagem: str) -> EstadoSistema:
    return {
        "mensagem_usuario": mensagem.strip(),
        "dentro_do_escopo": False,
        "motivo_rejeicao": None,
        "categoria_encaminhamento": None,
        "padrao_execucao": None,
        "justificativa_padrao": None,
        "perfil_extraido": None,
        "query_busca": None,
        "documentos_encontrados": None,
        "plano_rewoo": None,
        "evidencias_rewoo": None,
        "analise_elegibilidade": None,
        "critica_reflexion": None,
        "iteracao_reflexion": 0,
        "historico_reflexion": [],
        "modelos_utilizados": {},
        "resposta_beneficios": None,
        "mensagem_apoio": None,
        "resposta_final": "",
        "status_api": STATUS_INICIADO,
    }


def executar_fluxo(mensagem: str) -> EstadoSistema:
    """Executa o grafo multiagente para a mensagem do usuário e retorna o EstadoSistema final."""
    return app.invoke(estado_inicial(mensagem))
