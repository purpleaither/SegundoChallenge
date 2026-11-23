"""Orquestração multiagente em LangGraph com roteamento dinâmico entre Padrão, ReWOO e Reflexion."""

from pathlib import Path
import sys

from dotenv import load_dotenv

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))
load_dotenv(PASTA_ATUAL / ".env")

from langgraph.graph import END, START, StateGraph

if __package__:
    from .agents import (
        MAX_ITERACOES_REFLEXION,
        STATUS_BLOQUEADO,
        STATUS_DEGRADADO,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        agente_analista_elegibilidade,
        agente_comunicador,
        agente_extrator_perfil,
        agente_fallback_rag,
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
else:
    from agents import (
        MAX_ITERACOES_REFLEXION,
        STATUS_BLOQUEADO,
        STATUS_DEGRADADO,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        agente_analista_elegibilidade,
        agente_comunicador,
        agente_extrator_perfil,
        agente_fallback_rag,
        agente_guardrail,
        agente_reflexion_critico,
        agente_reflexion_revisor,
        agente_retriever,
        agente_rewoo_planner,
        agente_rewoo_solver,
        agente_rewoo_worker,
        consolidar_encaminhamento_ajuda,
    )
    from schemas import STATUS_INICIADO, EstadoSistema


def rotear_pos_guardrail(state: EstadoSistema) -> str:
    """Encerra se fora de escopo/erro; em modo degradado vai direto ao RAG; senão segue ReWOO ou Padrão."""
    if (
        not state.get("dentro_do_escopo")
        or state.get("status_api") in (STATUS_ERRO_API, STATUS_BLOQUEADO, STATUS_ENCAMINHAMENTO_AJUDA)
    ):
        return END
    if state.get("modo_degradado"):
        return "retriever"
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


def _rotear_ou_degradar(proximo_no: str):
    """Encaminha ao próximo nó, ou ao fallback determinístico RAG em modo degradado, ou ao consolidador em erro."""
    def _roteador(state: EstadoSistema) -> str:
        if state.get("status_api") == STATUS_ERRO_API:
            return "consolidar_encaminhamento_ajuda"
        if state.get("modo_degradado"):
            return "fallback_rag"
        return proximo_no

    return _roteador


def rotear_pos_comunicador(state: EstadoSistema) -> str:
    """No padrão 'padrao' consolida saída; em modo degradado usa fallback RAG; no 'reflexion' vai ao Crítico."""
    if state.get("status_api") == STATUS_ERRO_API:
        return "consolidar_encaminhamento_ajuda"
    if state.get("modo_degradado"):
        return "fallback_rag"
    if state.get("padrao_execucao") == "reflexion":
        return "reflexion_critico"
    return "consolidar_encaminhamento_ajuda"


def rotear_pos_critico(state: EstadoSistema) -> str:
    """Consolida saída se aprovado, degradado, erro ou limite atingido; senão revisa."""
    if state.get("status_api") in (STATUS_ERRO_API, STATUS_DEGRADADO) or state.get("modo_degradado"):
        return "consolidar_encaminhamento_ajuda"
    critica = state.get("critica_reflexion") or {}
    iteracao = int(state.get("iteracao_reflexion") or 0)
    if critica.get("aprovado") is True or iteracao >= MAX_ITERACOES_REFLEXION:
        return "consolidar_encaminhamento_ajuda"
    return "reflexion_revisor"


def rotear_pos_revisor(state: EstadoSistema) -> str:
    """Retorna ao Crítico ou consolida imediatamente em erro/modo degradado preservando o rascunho."""
    if state.get("status_api") in (STATUS_ERRO_API, STATUS_DEGRADADO) or state.get("modo_degradado"):
        return "consolidar_encaminhamento_ajuda"
    return "reflexion_critico"


def rotear_pos_rewoo_planner(state: EstadoSistema) -> str:
    """Segue para o Worker ou aplica downgrade limpo para o fluxo 'padrao' se o Planner falhou."""
    if state.get("status_api") == STATUS_ERRO_API:
        return "consolidar_encaminhamento_ajuda"
    if state.get("padrao_execucao") == "padrao":
        return "extrator_perfil"
    return "rewoo_worker"


def rotear_pos_rewoo_solver(state: EstadoSistema) -> str:
    """Encaminha ao fallback determinístico RAG se o Solver degradou; caso contrário consolida."""
    if state.get("modo_degradado") and state.get("status_api") != STATUS_ERRO_API:
        return "fallback_rag"
    return "consolidar_encaminhamento_ajuda"


def construir_grafo():
    workflow = StateGraph(EstadoSistema)

    # 1. Registro dos nós (Guardrail/Seletor + Padrão + ReWOO + Reflexion + Fallback RAG + Consolidador)
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
    workflow.add_node("fallback_rag", agente_fallback_rag)
    workflow.add_node("consolidar_encaminhamento_ajuda", consolidar_encaminhamento_ajuda)

    # 2. Entrada e roteamento dinâmico pós-Guardrail
    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges(
        "guardrail",
        rotear_pos_guardrail,
        {
            "extrator_perfil": "extrator_perfil",
            "retriever": "retriever",
            "rewoo_planner": "rewoo_planner",
            END: END,
        },
    )

    # 3. Caminho Padrão + Base do Reflexion + Degradação Graciosa
    workflow.add_conditional_edges(
        "extrator_perfil",
        _rotear_ou_encerrar("retriever"),
        {"retriever": "retriever", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_conditional_edges(
        "retriever",
        _rotear_ou_degradar("analista_elegibilidade"),
        {
            "analista_elegibilidade": "analista_elegibilidade",
            "fallback_rag": "fallback_rag",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_conditional_edges(
        "analista_elegibilidade",
        _rotear_ou_degradar("comunicador"),
        {
            "comunicador": "comunicador",
            "fallback_rag": "fallback_rag",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_conditional_edges(
        "comunicador",
        rotear_pos_comunicador,
        {
            "reflexion_critico": "reflexion_critico",
            "fallback_rag": "fallback_rag",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )

    # 4. Ciclo Reflexion (Crítico <-> Revisor com limite MAX_ITERACOES_REFLEXION e preservação de rascunho)
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
        rotear_pos_revisor,
        {"reflexion_critico": "reflexion_critico", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )

    # 5. Caminho ReWOO (Planner -> Worker -> Solver -> Consolidador, com downgrade e fallback RAG)
    workflow.add_conditional_edges(
        "rewoo_planner",
        rotear_pos_rewoo_planner,
        {
            "rewoo_worker": "rewoo_worker",
            "extrator_perfil": "extrator_perfil",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_conditional_edges(
        "rewoo_worker",
        _rotear_ou_encerrar("rewoo_solver"),
        {"rewoo_solver": "rewoo_solver", "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda"},
    )
    workflow.add_conditional_edges(
        "rewoo_solver",
        rotear_pos_rewoo_solver,
        {
            "fallback_rag": "fallback_rag",
            "consolidar_encaminhamento_ajuda": "consolidar_encaminhamento_ajuda",
        },
    )
    workflow.add_edge("fallback_rag", "consolidar_encaminhamento_ajuda")
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
        "modo_degradado": False,
        "eventos_fallback": [],
        "resposta_beneficios": None,
        "mensagem_apoio": None,
        "resposta_final": "",
        "status_api": STATUS_INICIADO,
    }


def executar_fluxo(mensagem: str) -> EstadoSistema:
    """Executa o grafo multiagente para a mensagem do usuário e retorna o EstadoSistema final."""
    return app.invoke(estado_inicial(mensagem))
