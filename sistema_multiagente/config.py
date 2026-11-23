"""Configuração centralizada, escalonamento por tiers cognitivos e fallback de modelos Gemini."""

import os
from pathlib import Path
from typing import TypeVar
import warnings

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")

PASTA_ATUAL = Path(__file__).resolve().parent
load_dotenv(PASTA_ATUAL / ".env")
load_dotenv()

if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("Erro: GOOGLE_API_KEY não encontrada no arquivo .env")

T = TypeVar("T", bound=BaseModel)

# Tiers cognitivos verificados empiricamente na API Gemini do ambiente
TIER_RAPIDO = "rapido"
TIER_EQUILIBRADO = "equilibrado"
TIER_ANALITICO = "analitico"

CONFIG_TIERS: dict[str, dict] = {
    TIER_RAPIDO: {
        "descricao": "Classificação rápida de escopo/roteamento e extração estruturada",
        "modelo_principal": "gemini-3.1-flash-lite",
        "fallbacks": ("gemini-3.5-flash-lite", "gemini-4-hydrogen"),
        "temperature": 0.0,
        "timeout": 45,
    },
    TIER_EQUILIBRADO: {
        "descricao": "Planejamento de subconsultas, comunicação acessível e revisão guiada",
        "modelo_principal": "gemini-3.5-flash-lite",
        "fallbacks": ("gemini-3.1-flash-lite", "gemini-4-hydrogen"),
        "temperature": 0.0,
        "timeout": 60,
    },
    TIER_ANALITICO: {
        "descricao": "Raciocínio estrito de elegibilidade (RIA02), síntese ReWOO e crítica Reflexion",
        "modelo_principal": "gemini-4-hydrogen",
        "fallbacks": ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"),
        "temperature": 0.0,
        "timeout": 75,
    },
}

TIER_POR_AGENTE: dict[str, str] = {
    "guardrail": TIER_RAPIDO,
    "extrator_perfil": TIER_RAPIDO,
    "comunicador": TIER_EQUILIBRADO,
    "rewoo_planner": TIER_EQUILIBRADO,
    "rewoo_comunicador": TIER_EQUILIBRADO,
    "reflexion_revisor": TIER_EQUILIBRADO,
    "analista_elegibilidade": TIER_ANALITICO,
    "rewoo_solver": TIER_ANALITICO,
    "reflexion_critico": TIER_ANALITICO,
}

_CACHE_LLMS: dict[tuple[str, float, int], ChatGoogleGenerativeAI] = {}
_MODELOS_BLOQUEADOS_SESSAO: set[str] = set()


def obter_llm(nome_modelo: str, temperature: float = 0.0, timeout: int = 30) -> ChatGoogleGenerativeAI:
    """Retorna instância cacheada do ChatGoogleGenerativeAI para o modelo e parâmetros informados."""
    chave = (nome_modelo, temperature, timeout)
    if chave not in _CACHE_LLMS:
        _CACHE_LLMS[chave] = ChatGoogleGenerativeAI(
            model=nome_modelo,
            temperature=temperature,
            max_retries=1,
            timeout=timeout,
        )
    return _CACHE_LLMS[chave]


def cadeia_modelos_agente(agente: str) -> tuple[list[str], float, int]:
    """Resolve a lista ordenada [modelo_principal, *fallbacks], temperatura e timeout para um agente."""
    tier = TIER_POR_AGENTE.get(agente, TIER_EQUILIBRADO)
    cfg = CONFIG_TIERS[tier]
    todos = [cfg["modelo_principal"], *cfg["fallbacks"]]
    disponiveis = [m for m in todos if m not in _MODELOS_BLOQUEADOS_SESSAO] or todos
    return disponiveis, float(cfg["temperature"]), int(cfg["timeout"])


def _eh_erro_permanente_sessao(erro: Exception) -> bool:
    msg = str(erro)
    return any(s in msg for s in ("NOT_FOUND", "no longer available", "404", "RESOURCE_EXHAUSTED", "429"))


def _eh_erro_recuperavel_modelo(erro: Exception) -> bool:
    msg = str(erro)
    sinais = (
        "NOT_FOUND",
        "no longer available",
        "404",
        "429",
        "503",
        "504",
        "UNAVAILABLE",
        "RESOURCE_EXHAUSTED",
        "DEADLINE_EXCEEDED",
        "Timeout",
        "timed out",
    )
    return any(s in msg for s in sinais)


def invocar_estruturado(
    agente: str,
    schema: type[T],
    prompt_sistema: str,
    prompt_usuario: str,
) -> tuple[T, str]:
    """Invoca o LLM escalado para `agente` com `.with_structured_output(schema)` e fallback limpo."""
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]
    modelos, temperatura, timeout = cadeia_modelos_agente(agente)
    ultimo_erro: Exception | None = None

    for idx, nome_modelo in enumerate(modelos):
        try:
            modelo = obter_llm(nome_modelo, temperature=temperatura, timeout=timeout)
            resultado = modelo.with_structured_output(schema).invoke(mensagens)
            if resultado is None:
                raise ValueError(f"Saída estruturada vazia em '{nome_modelo}' para {schema.__name__}.")
            return resultado, nome_modelo
        except Exception as erro:
            ultimo_erro = erro
            if _eh_erro_permanente_sessao(erro):
                _MODELOS_BLOQUEADOS_SESSAO.add(nome_modelo)
            tem_proximo = idx < len(modelos) - 1
            if not tem_proximo or not (_eh_erro_recuperavel_modelo(erro) or isinstance(erro, ValueError)):
                raise

    assert ultimo_erro is not None
    raise ultimo_erro


def invocar_texto(
    agente: str,
    prompt_sistema: str,
    prompt_usuario: str,
) -> tuple[str, str]:
    """Invoca o LLM escalado para `agente` retornando `(texto_gerado, nome_modelo_utilizado)`."""
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]
    modelos, temperatura, timeout = cadeia_modelos_agente(agente)
    ultimo_erro: Exception | None = None

    for idx, nome_modelo in enumerate(modelos):
        try:
            modelo = obter_llm(nome_modelo, temperature=temperatura, timeout=timeout)
            resposta = modelo.invoke(mensagens)
            texto = (getattr(resposta, "text", None) or str(resposta.content)).strip()
            if not texto:
                raise ValueError(f"Resposta textual vazia em '{nome_modelo}'.")
            return texto, nome_modelo
        except Exception as erro:
            ultimo_erro = erro
            if _eh_erro_permanente_sessao(erro):
                _MODELOS_BLOQUEADOS_SESSAO.add(nome_modelo)
            tem_proximo = idx < len(modelos) - 1
            if not tem_proximo or not (_eh_erro_recuperavel_modelo(erro) or isinstance(erro, ValueError)):
                raise

    assert ultimo_erro is not None
    raise ultimo_erro


# Instância padrão exportada por compatibilidade com importações diretas
llm = obter_llm(CONFIG_TIERS[TIER_EQUILIBRADO]["modelo_principal"], temperature=0.0)

