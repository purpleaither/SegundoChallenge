"""Configuração centralizada, escalonamento por tiers cognitivos, resiliência e fallback multi-provedor."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, TypeVar
import warnings

from dotenv import load_dotenv
import httpx
from langchain_core.exceptions import (
    ModelAPIError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelNotFoundError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
    ModelRefusalError,
    ModelTimeoutError,
    OutputParserException,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

try:
    import httpx2  # type: ignore[import-not-found]

    _HTTPX2_TRANSIENT: tuple[type[BaseException], ...] = (
        httpx2.TimeoutException,
        httpx2.TransportError,
    )
    _HTTPX2_CONNECT: tuple[type[BaseException], ...] = (httpx2.ConnectError,)
except Exception:  # pragma: no cover - opcional caso httpx2 não esteja instalado
    _HTTPX2_TRANSIENT = ()
    _HTTPX2_CONNECT = ()

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))

if __package__:
    from .llm_providers import (  # noqa: E402
        PROVEDORES_SECUNDARIOS,
        eh_modelo_secundario_local,
        extrair_texto_resposta,
        sanitizar_mensagem_erro,
    )
else:
    from llm_providers import (  # noqa: E402
        PROVEDORES_SECUNDARIOS,
        eh_modelo_secundario_local,
        extrair_texto_resposta,
        sanitizar_mensagem_erro,
    )

warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")

load_dotenv(PASTA_ATUAL / ".env")
load_dotenv()

if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

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

# Taxonomia de erros LLM
ERRO_PERMANENTE_MODELO = "permanente_modelo"
ERRO_AUTENTICACAO_PROVEDOR = "autenticacao_provedor"
ERRO_SEGURANCA_RECUSA = "seguranca_recusa"
ERRO_PARSING_ESTRUTURADO = "parsing_estruturado"
ERRO_TRANSITORIO = "transitorio"
ERRO_NAO_RECUPERAVEL = "nao_recuperavel"

_STATUS_HTTP_TRANSITORIOS = frozenset({408, 429, 500, 502, 503, 504, 529})

_SINAIS_PERMANENTE_MODELO = (
    "not_found",
    "no longer available",
    "model not found",
    "not found for api version",
    "404",
)
_SINAIS_AUTENTICACAO = (
    "api_key_invalid",
    "invalid api key",
    "api key not valid",
    "permission_denied",
    "unauthenticated",
    "unauthorized",
    "401",
    "403",
)
_SINAIS_SEGURANCA = (
    "safety",
    "harm_category",
    "prohibited_content",
    "dangerous_content",
    "blocklist",
    "blocked",
    "finish_reason",
    "saída estruturada vazia",
    "saida estruturada vazia",
)
_SINAIS_TRANSITORIOS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "529",
    "resource_exhausted",
    "unavailable",
    "overloaded",
    "high demand",
    "currently experiencing high demand",
    "deadline_exceeded",
    "bad gateway",
    "internal error",
    "internal server error",
    "rate limit",
    "rate_limit",
    "quota",
    "timeout",
    "timed out",
    "connecterror",
    "connection refused",
    "connection reset",
    "temporarily unavailable",
    "try again later",
)

# Relógio e sleep injetáveis para testes determinísticos sem espera real
_relogio: Callable[[], float] = time.monotonic
_dormir: Callable[[float], None] = time.sleep


class _CircuitBreakerLLM:
    """Gerencia quarentena permanente (404/auth) e cooldown temporário com TTL (429/503/rede)."""

    def __init__(self) -> None:
        self.permanentes: set[str] = set()
        self.provedores_bloqueados: set[str] = set()
        self.cooldown_ate: dict[str, float] = {}
        self.falhas_consecutivas: dict[str, int] = {}

    def resetar(self) -> None:
        self.permanentes.clear()
        self.provedores_bloqueados.clear()
        self.cooldown_ate.clear()
        self.falhas_consecutivas.clear()

    def esta_disponivel(self, chave: str, provedor: str | None = None) -> bool:
        if provedor and provedor in self.provedores_bloqueados:
            return False
        if chave in self.permanentes:
            return False
        agora = _relogio()
        for alvo in (chave, f"provedor:{provedor}" if provedor else None):
            if alvo and alvo in self.cooldown_ate:
                if agora < self.cooldown_ate[alvo]:
                    return False
                # TTL expirado -> permite sonda half-open
                self.cooldown_ate.pop(alvo, None)
        return True

    def registrar_sucesso(self, chave: str, provedor: str | None = None) -> None:
        self.cooldown_ate.pop(chave, None)
        self.falhas_consecutivas.pop(chave, None)
        if provedor:
            self.cooldown_ate.pop(f"provedor:{provedor}", None)
            self.falhas_consecutivas.pop(f"provedor:{provedor}", None)

    def registrar_falha(
        self,
        chave: str,
        categoria: str,
        provedor: str | None = None,
        cooldown_base: float = 60.0,
        cooldown_max: float = 300.0,
        bloquear_provedor_em_cooldown: bool = False,
    ) -> None:
        if categoria == ERRO_PERMANENTE_MODELO:
            self.permanentes.add(chave)
            return
        if categoria == ERRO_AUTENTICACAO_PROVEDOR:
            if provedor:
                self.provedores_bloqueados.add(provedor)
            else:
                self.permanentes.add(chave)
            return
        if categoria == ERRO_TRANSITORIO:
            alvo = f"provedor:{provedor}" if (bloquear_provedor_em_cooldown and provedor) else chave
            n_falhas = self.falhas_consecutivas.get(alvo, 0) + 1
            self.falhas_consecutivas[alvo] = n_falhas
            duracao = min(cooldown_max, cooldown_base * (2 ** (n_falhas - 1)))
            self.cooldown_ate[alvo] = _relogio() + duracao


_CACHE_LLMS: dict[tuple[str, float, int], ChatGoogleGenerativeAI] = {}
_CIRCUIT_BREAKER = _CircuitBreakerLLM()


def resetar_circuit_breaker() -> None:
    """Limpa o estado do circuit breaker e o cache de clientes (útil em testes unitários)."""
    _CIRCUIT_BREAKER.resetar()
    _CACHE_LLMS.clear()


def _int_env(nome: str, padrao: int, minimo: int = 1, maximo: int | None = None) -> int:
    bruto = os.getenv(nome, "").strip()
    if not bruto:
        return padrao
    try:
        valor = int(bruto)
    except ValueError:
        return padrao
    valor = max(minimo, valor)
    if maximo is not None:
        valor = min(maximo, valor)
    return valor


def _float_env(nome: str, padrao: float, minimo: float = 0.0) -> float:
    bruto = os.getenv(nome, "").strip()
    if not bruto:
        return padrao
    try:
        return max(minimo, float(bruto))
    except ValueError:
        return padrao


def _obter_max_tentativas() -> int:
    return _int_env("LLM_MAX_TENTATIVAS", 2, minimo=1, maximo=5)


def _obter_cooldown_config() -> tuple[float, float]:
    base = _float_env("LLM_COOLDOWN_SEGUNDOS", 60.0, minimo=0.0)
    maximo = _float_env("LLM_COOLDOWN_MAX_SEGUNDOS", max(300.0, base), minimo=base)
    return base, maximo


def _obter_ordem_provedores_secundarios() -> list[str]:
    bruto = os.getenv("LLM_FALLBACK_ORDER", "").strip()
    if not bruto:
        return []
    ordem: list[str] = []
    for item in bruto.split(","):
        nome = item.strip().lower()
        if nome in PROVEDORES_SECUNDARIOS and nome not in ordem:
            ordem.append(nome)
    return ordem


def _resolver_config_tier(tier: str) -> tuple[list[str], float, int]:
    cfg = CONFIG_TIERS[tier]
    sufixo = tier.upper()
    principal = os.getenv(f"GEMINI_MODELO_{sufixo}", "").strip() or cfg["modelo_principal"]

    fallbacks_env = os.getenv(f"GEMINI_FALLBACKS_{sufixo}", "").strip()
    if fallbacks_env:
        fallbacks = [m.strip() for m in fallbacks_env.split(",") if m.strip()]
    else:
        fallbacks = list(cfg["fallbacks"])

    modelos = list(dict.fromkeys([principal, *fallbacks]))
    timeout_padrao_env = os.getenv("LLM_TIMEOUT_PADRAO", "").strip()
    timeout_base = int(timeout_padrao_env) if timeout_padrao_env.isdigit() else int(cfg["timeout"])
    timeout = _int_env(f"LLM_TIMEOUT_{sufixo}", timeout_base, minimo=5)
    return modelos, float(cfg["temperature"]), timeout


def _obter_chave_gemini() -> str:
    chave = os.getenv("GOOGLE_API_KEY", "").strip()
    if chave:
        return chave
    chave_alt = os.getenv("GEMINI_API_KEY", "").strip()
    if chave_alt:
        os.environ["GOOGLE_API_KEY"] = chave_alt
        return chave_alt
    return ""


def obter_llm(nome_modelo: str, temperature: float = 0.0, timeout: int = 30) -> ChatGoogleGenerativeAI:
    """Retorna instância cacheada do ChatGoogleGenerativeAI (max_retries=1 para controle via tenacity)."""
    if not _obter_chave_gemini():
        raise ValueError("GOOGLE_API_KEY (ou GEMINI_API_KEY) não configurada no ambiente/.env.")
    chave = (nome_modelo, temperature, timeout)
    if chave not in _CACHE_LLMS:
        # Em langchain-google-genai 4.5+, max_retries=1 mapeia para HttpRetryOptions(attempts=1),
        # evitando retries ocultos duplicados dentro do SDK e deixando o backoff sob controle explícito.
        _CACHE_LLMS[chave] = ChatGoogleGenerativeAI(
            model=nome_modelo,
            temperature=temperature,
            max_retries=1,
            timeout=timeout,
        )
    return _CACHE_LLMS[chave]


def cadeia_modelos_agente(agente: str) -> tuple[list[str], float, int]:
    """Resolve a lista ordenada de modelos Gemini disponíveis (respeitando TTL/404), temperatura e timeout."""
    tier = TIER_POR_AGENTE.get(agente, TIER_EQUILIBRADO)
    todos, temperatura, timeout = _resolver_config_tier(tier)
    disponiveis = [m for m in todos if _CIRCUIT_BREAKER.esta_disponivel(m, provedor="gemini")]
    return disponiveis, temperatura, timeout


def _extrair_codigo_http(erro: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        valor = getattr(erro, attr, None)
        if isinstance(valor, int):
            return valor
    resp = getattr(erro, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)
        if isinstance(status, int):
            return status
    return None


def _iterar_cadeia_excecoes(erro: BaseException) -> list[BaseException]:
    visitados: set[int] = set()
    fila: list[BaseException] = [erro]
    resultado: list[BaseException] = []
    while fila:
        atual = fila.pop(0)
        if id(atual) in visitados:
            continue
        visitados.add(id(atual))
        resultado.append(atual)
        for prox in (getattr(atual, "__cause__", None), getattr(atual, "__context__", None)):
            if isinstance(prox, BaseException):
                fila.append(prox)
    return resultado


def _eh_erro_conexao_recusada(erro: BaseException) -> bool:
    tipos_connect = (httpx.ConnectError, ConnectionRefusedError, *_HTTPX2_CONNECT)
    for exc in _iterar_cadeia_excecoes(erro):
        if isinstance(exc, tipos_connect):
            return True
    msg = str(erro).lower()
    return "connection refused" in msg or "connecterror" in msg


def classificar_erro_llm(erro: BaseException) -> str:
    """Classifica exceções LLM primeiro por tipo/HTTP status e depois por sinais case-insensitive."""
    cadeia = _iterar_cadeia_excecoes(erro)
    tipos_transitorios = (
        ModelRateLimitError,
        ModelAPIError,
        ModelTimeoutError,
        ModelConnectionError,
        httpx.TimeoutException,
        httpx.TransportError,
        TimeoutError,
        ConnectionError,
        *_HTTPX2_TRANSIENT,
    )

    # 1. Verificação por tipo explícito e código HTTP
    for exc in cadeia:
        if isinstance(exc, ModelNotFoundError):
            return ERRO_PERMANENTE_MODELO
        if isinstance(exc, (ModelAuthenticationError, ModelPermissionDeniedError)):
            return ERRO_AUTENTICACAO_PROVEDOR
        if isinstance(exc, ModelRefusalError):
            return ERRO_SEGURANCA_RECUSA

        codigo = _extrair_codigo_http(exc)
        if codigo == 404:
            return ERRO_PERMANENTE_MODELO
        if codigo in (401, 403):
            return ERRO_AUTENTICACAO_PROVEDOR
        if codigo in _STATUS_HTTP_TRANSITORIOS:
            return ERRO_TRANSITORIO

        if isinstance(exc, tipos_transitorios):
            return ERRO_TRANSITORIO

    # 2. Verificação textual case-insensitive (mensagens de SDK/HTTP/mocks)
    msg = " | ".join(str(exc) for exc in cadeia).lower()
    if any(s in msg for s in _SINAIS_SEGURANCA):
        return ERRO_SEGURANCA_RECUSA
    if any(s in msg for s in _SINAIS_PERMANENTE_MODELO):
        return ERRO_PERMANENTE_MODELO
    if any(s in msg for s in _SINAIS_AUTENTICACAO):
        return ERRO_AUTENTICACAO_PROVEDOR
    if any(s in msg for s in _SINAIS_TRANSITORIOS):
        return ERRO_TRANSITORIO

    # 3. Parsing / validação estruturada / resposta vazia
    for exc in cadeia:
        if isinstance(exc, (OutputParserException, ValidationError, json.JSONDecodeError, ValueError)):
            return ERRO_PARSING_ESTRUTURADO

    return ERRO_NAO_RECUPERAVEL


def _eh_erro_permanente_sessao(erro: Exception) -> bool:
    """Retorna True apenas para falhas realmente permanentes do modelo (ex.: 404), nunca 429."""
    return classificar_erro_llm(erro) == ERRO_PERMANENTE_MODELO


def _eh_erro_recuperavel_modelo(erro: Exception) -> bool:
    """Retorna True quando o erro permite failover para outro modelo ou provedor."""
    return classificar_erro_llm(erro) in (
        ERRO_PERMANENTE_MODELO,
        ERRO_AUTENTICACAO_PROVEDOR,
        ERRO_SEGURANCA_RECUSA,
        ERRO_PARSING_ESTRUTURADO,
        ERRO_TRANSITORIO,
    )


def _executar_com_retry(
    fn: Callable[[], T],
    max_tentativas: int,
    fail_fast_conexao: bool = False,
) -> T:
    """Executa uma chamada com backoff exponencial + jitter apenas em erros transitórios."""
    if max_tentativas <= 1:
        return fn()

    def _deve_retentar(exc: BaseException) -> bool:
        if fail_fast_conexao and _eh_erro_conexao_recusada(exc):
            return False
        return classificar_erro_llm(exc) == ERRO_TRANSITORIO

    retrying = Retrying(
        stop=stop_after_attempt(max_tentativas),
        wait=wait_exponential_jitter(initial=0.8, max=5.0, jitter=0.5),
        retry=retry_if_exception(_deve_retentar),
        sleep=_dormir,
        reraise=True,
    )
    return retrying(fn)


def _invocar_com_fallback(
    agente: str,
    executar_gemini: Callable[[str, float, int], T],
    executar_secundario: Callable[[object, str, float, int], tuple[T, str]],
) -> tuple[T, str]:
    """Orquestra Camada 1 (tiers Gemini + tenacity + TTL) e Camada 2 (provedores secundários opt-in)."""
    tier = TIER_POR_AGENTE.get(agente, TIER_EQUILIBRADO)
    modelos_gemini, temperatura, timeout = cadeia_modelos_agente(agente)
    max_tentativas = _obter_max_tentativas()
    cooldown_base, cooldown_max = _obter_cooldown_config()

    ultimo_erro: Exception | None = None
    erro_seguranca_gemini: Exception | None = None

    # Camada 1 — Google Gemini (se GOOGLE_API_KEY/GEMINI_API_KEY estiver configurada e circuito permitir)
    if _obter_chave_gemini():
        for nome_modelo in modelos_gemini:
            try:
                resultado = _executar_com_retry(
                    lambda m=nome_modelo: executar_gemini(m, temperatura, timeout),
                    max_tentativas=max_tentativas,
                )
                _CIRCUIT_BREAKER.registrar_sucesso(nome_modelo, provedor="gemini")
                return resultado, nome_modelo
            except Exception as erro:
                ultimo_erro = erro
                categoria = classificar_erro_llm(erro)
                if categoria == ERRO_SEGURANCA_RECUSA and erro_seguranca_gemini is None:
                    erro_seguranca_gemini = erro
                _CIRCUIT_BREAKER.registrar_falha(
                    nome_modelo,
                    categoria=categoria,
                    provedor="gemini",
                    cooldown_base=cooldown_base,
                    cooldown_max=cooldown_max,
                )
                if categoria == ERRO_NAO_RECUPERAVEL:
                    raise
                if categoria == ERRO_AUTENTICACAO_PROVEDOR:
                    break

    # Camada 2 — Provedores secundários opt-in (ex.: Ollama local e/ou OpenAI-compatible)
    for nome_provedor in _obter_ordem_provedores_secundarios():
        provedor = PROVEDORES_SECUNDARIOS[nome_provedor]
        if not provedor.esta_configurado():
            continue
        chave_cb = f"provedor:{nome_provedor}"
        if not _CIRCUIT_BREAKER.esta_disponivel(chave_cb, provedor=nome_provedor):
            continue
        eh_local = nome_provedor == "ollama"
        try:
            resultado, modelo_rotulo = _executar_com_retry(
                lambda p=provedor: executar_secundario(p, tier, temperatura, timeout),
                max_tentativas=1 if eh_local else max_tentativas,
                fail_fast_conexao=eh_local,
            )
            _CIRCUIT_BREAKER.registrar_sucesso(chave_cb, provedor=nome_provedor)
            return resultado, modelo_rotulo
        except Exception as erro:
            # Preserva sinal de bloqueio SAFETY do Gemini caso o fallback local esteja offline
            if erro_seguranca_gemini is not None and _eh_erro_conexao_recusada(erro):
                ultimo_erro = erro_seguranca_gemini
            else:
                ultimo_erro = erro
            categoria = classificar_erro_llm(erro)
            _CIRCUIT_BREAKER.registrar_falha(
                chave_cb,
                categoria=categoria,
                provedor=nome_provedor,
                cooldown_base=cooldown_base,
                cooldown_max=cooldown_max,
                bloquear_provedor_em_cooldown=True,
            )
            if categoria == ERRO_NAO_RECUPERAVEL:
                raise

    if ultimo_erro is not None:
        raise ultimo_erro
    raise RuntimeError(
        "Nenhum provedor LLM disponível no momento (GOOGLE_API_KEY ausente ou circuit breaker ativo)."
    )


def invocar_estruturado(
    agente: str,
    schema: type[T],
    prompt_sistema: str,
    prompt_usuario: str,
) -> tuple[T, str]:
    """Invoca o LLM escalado para `agente` com saída estruturada Pydantic, retry e fallback."""
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]

    def _chamar_gemini(nome_modelo: str, temperatura: float, timeout: int) -> T:
        modelo = obter_llm(nome_modelo, temperature=temperatura, timeout=timeout)
        resultado = modelo.with_structured_output(schema).invoke(mensagens)
        if resultado is None:
            raise ValueError(f"Saída estruturada vazia em '{nome_modelo}' para {schema.__name__}.")
        return resultado

    def _chamar_secundario(provedor, tier: str, temperatura: float, timeout: int) -> tuple[T, str]:
        return provedor.invocar_estruturado(
            tier=tier,
            schema=schema,
            prompt_sistema=prompt_sistema,
            prompt_usuario=prompt_usuario,
            temperature=temperatura,
            timeout_tier=timeout,
        )

    return _invocar_com_fallback(agente, _chamar_gemini, _chamar_secundario)


def invocar_texto(
    agente: str,
    prompt_sistema: str,
    prompt_usuario: str,
) -> tuple[str, str]:
    """Invoca o LLM escalado para `agente` retornando `(texto_gerado, nome_modelo_utilizado)`."""
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]

    def _chamar_gemini(nome_modelo: str, temperatura: float, timeout: int) -> str:
        modelo = obter_llm(nome_modelo, temperature=temperatura, timeout=timeout)
        resposta = modelo.invoke(mensagens)
        texto = extrair_texto_resposta(resposta)
        if not texto:
            raise ValueError(f"Resposta textual vazia em '{nome_modelo}'.")
        return texto

    def _chamar_secundario(provedor, tier: str, temperatura: float, timeout: int) -> tuple[str, str]:
        return provedor.invocar_texto(
            tier=tier,
            prompt_sistema=prompt_sistema,
            prompt_usuario=prompt_usuario,
            temperature=temperatura,
            timeout_tier=timeout,
        )

    return _invocar_com_fallback(agente, _chamar_gemini, _chamar_secundario)


def __getattr__(name: str):
    """Compatibilidade lazy com importações diretas de `config.llm` sem falhar no import."""
    if name == "llm":
        return obter_llm(CONFIG_TIERS[TIER_EQUILIBRADO]["modelo_principal"], temperature=0.0)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CONFIG_TIERS",
    "ERRO_AUTENTICACAO_PROVEDOR",
    "ERRO_NAO_RECUPERAVEL",
    "ERRO_PARSING_ESTRUTURADO",
    "ERRO_PERMANENTE_MODELO",
    "ERRO_SEGURANCA_RECUSA",
    "ERRO_TRANSITORIO",
    "TIER_ANALITICO",
    "TIER_EQUILIBRADO",
    "TIER_POR_AGENTE",
    "TIER_RAPIDO",
    "cadeia_modelos_agente",
    "classificar_erro_llm",
    "eh_modelo_secundario_local",
    "invocar_estruturado",
    "invocar_texto",
    "obter_llm",
    "resetar_circuit_breaker",
    "sanitizar_mensagem_erro",
]
