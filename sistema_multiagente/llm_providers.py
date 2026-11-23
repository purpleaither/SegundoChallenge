"""Adaptadores HTTP leves (via httpx) para provedores LLM secundários opt-in (Ollama e OpenAI-compatible).

Mantém zero novas dependências externas, aderência à LGPD (provedores externos só são
acionados mediante configuração explícita no ambiente) e sanitização rigorosa de erros.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_PADROES_SEGREDOS_ERRO: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&](?:key|api_key|token)=)[^&\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(x-goog-api-key\s*[:=]\s*)[^\s,;\"']+"), r"\1[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bsk-[0-9A-Za-z\-_]{16,}\b"), "[REDACTED_KEY]"),
)


def sanitizar_mensagem_erro(erro: Exception, limite: int = 200) -> str:
    """Formata erro de forma segura, removendo eventuais segredos e limitando o tamanho."""
    texto = f"{type(erro).__name__}: {erro}"
    for padrao, substituto in _PADROES_SEGREDOS_ERRO:
        texto = padrao.sub(substituto, texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:limite]


def extrair_texto_resposta(resposta: Any) -> str:
    """Extrai texto limpo de respostas LangChain (AIMessage) ou conteúdo bruto sem vazar '[]'."""
    if isinstance(resposta, str):
        return resposta.strip()

    texto_prop = getattr(resposta, "text", None)
    if isinstance(texto_prop, str) and texto_prop.strip():
        return texto_prop.strip()

    conteudo = getattr(resposta, "content", None)
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        partes: list[str] = []
        for bloco in conteudo:
            if isinstance(bloco, str) and bloco.strip():
                partes.append(bloco.strip())
            elif isinstance(bloco, dict):
                txt = bloco.get("text")
                if isinstance(txt, str) and txt.strip():
                    partes.append(txt.strip())
        return "\n".join(partes).strip()
    if conteudo is None:
        return ""
    return str(conteudo).strip()


def _limpar_json_bruto(conteudo: str) -> str:
    """Remove cercas markdown ```json ... ``` caso um modelo retorne JSON encapsulado."""
    texto = conteudo.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def _validar_json_pydantic(schema: type[T], conteudo: str, origem: str) -> T:
    texto = _limpar_json_bruto(conteudo)
    if not texto:
        raise ValueError(f"Saída estruturada vazia em '{origem}' para {schema.__name__}.")
    return schema.model_validate_json(texto)


def eh_modelo_secundario_local(nome_modelo: str | None) -> bool:
    """Indica se o modelo executado veio do provedor local Ollama."""
    return bool(nome_modelo and nome_modelo.startswith("ollama/"))


def _resolver_modelo_por_tier(prefixo_env: str, tier: str, padrao: str) -> str:
    especifico = os.getenv(f"{prefixo_env}_{tier.upper()}", "").strip()
    if especifico:
        return especifico
    return os.getenv(prefixo_env, padrao).strip()


def _float_env(nome: str, padrao: float, minimo: float = 0.5) -> float:
    bruto = os.getenv(nome, "").strip()
    if not bruto:
        return padrao
    try:
        return max(minimo, float(bruto))
    except ValueError:
        return padrao


class ProvedorOllama:
    """Cliente leve para o Ollama local (/api/chat) com constrained JSON nativo via `format`."""

    nome = "ollama"

    def esta_configurado(self) -> bool:
        return bool(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip())

    def _config(self, tier: str, timeout_tier: int) -> tuple[str, str, httpx.Timeout]:
        base_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        modelo = _resolver_modelo_por_tier("OLLAMA_LLM_MODEL", tier, "qwen2.5:7b")
        timeout_total = _float_env("OLLAMA_LLM_TIMEOUT", float(timeout_tier), minimo=5.0)
        timeout_conexao = _float_env("OLLAMA_CONNECT_TIMEOUT", 3.0, minimo=0.5)
        return base_url, modelo, httpx.Timeout(timeout_total, connect=min(timeout_conexao, timeout_total))

    def _post_chat(self, base_url: str, payload: dict[str, Any], timeout: httpx.Timeout) -> dict[str, Any]:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{base_url}/api/chat", json=payload)
            resp.raise_for_status()
            dados = resp.json()
        if not isinstance(dados, dict):
            raise ValueError("Resposta inválida do Ollama (JSON raiz não é objeto).")
        return dados

    def invocar_estruturado(
        self,
        tier: str,
        schema: type[T],
        prompt_sistema: str,
        prompt_usuario: str,
        temperature: float,
        timeout_tier: int,
    ) -> tuple[T, str]:
        base_url, modelo, timeout = self._config(tier, timeout_tier)
        identificador = f"ollama/{modelo}"
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            "stream": False,
            "options": {"temperature": temperature},
            "format": schema.model_json_schema(),
        }
        dados = self._post_chat(base_url, payload, timeout)
        conteudo = str((dados.get("message") or {}).get("content") or "")
        return _validar_json_pydantic(schema, conteudo, identificador), identificador

    def invocar_texto(
        self,
        tier: str,
        prompt_sistema: str,
        prompt_usuario: str,
        temperature: float,
        timeout_tier: int,
    ) -> tuple[str, str]:
        base_url, modelo, timeout = self._config(tier, timeout_tier)
        identificador = f"ollama/{modelo}"
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        dados = self._post_chat(base_url, payload, timeout)
        texto = str((dados.get("message") or {}).get("content") or "").strip()
        if not texto:
            raise ValueError(f"Resposta textual vazia em '{identificador}'.")
        return texto, identificador


class ProvedorOpenAICompativel:
    """Cliente opt-in para endpoints OpenAI-compatible (/chat/completions) como Groq/OpenRouter/OpenAI."""

    nome = "openai_compat"

    def esta_configurado(self) -> bool:
        return bool(
            os.getenv("LLM_FALLBACK_BASE_URL", "").strip()
            and os.getenv("LLM_FALLBACK_API_KEY", "").strip()
            and (
                os.getenv("LLM_FALLBACK_MODEL", "").strip()
                or os.getenv("LLM_FALLBACK_MODEL_RAPIDO", "").strip()
                or os.getenv("LLM_FALLBACK_MODEL_EQUILIBRADO", "").strip()
                or os.getenv("LLM_FALLBACK_MODEL_ANALITICO", "").strip()
            )
        )

    def _config(self, tier: str, timeout_tier: int) -> tuple[str, str, str, httpx.Timeout]:
        base_url = os.getenv("LLM_FALLBACK_BASE_URL", "").strip().rstrip("/")
        api_key = os.getenv("LLM_FALLBACK_API_KEY", "").strip()
        modelo = _resolver_modelo_por_tier("LLM_FALLBACK_MODEL", tier, "")
        if not base_url or not api_key or not modelo:
            raise ValueError(
                "Provedor openai_compat incompleto: configure LLM_FALLBACK_BASE_URL, "
                "LLM_FALLBACK_API_KEY e LLM_FALLBACK_MODEL."
            )
        timeout_total = _float_env("LLM_FALLBACK_TIMEOUT", min(float(timeout_tier), 45.0), minimo=5.0)
        timeout_conexao = _float_env("LLM_FALLBACK_CONNECT_TIMEOUT", 5.0, minimo=0.5)
        return base_url, api_key, modelo, httpx.Timeout(timeout_total, connect=min(timeout_conexao, timeout_total))

    def _post_completions(
        self,
        base_url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout: httpx.Timeout,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            dados = resp.json()
        if not isinstance(dados, dict):
            raise ValueError("Resposta inválida do provedor OpenAI-compatible.")
        return dados

    @staticmethod
    def _extrair_conteudo_choice(dados: dict[str, Any]) -> str:
        choices = dados.get("choices") or []
        if not choices or not isinstance(choices, list):
            return ""
        msg = choices[0].get("message") or {}
        return extrair_texto_resposta(msg.get("content"))

    def invocar_estruturado(
        self,
        tier: str,
        schema: type[T],
        prompt_sistema: str,
        prompt_usuario: str,
        temperature: float,
        timeout_tier: int,
    ) -> tuple[T, str]:
        base_url, api_key, modelo, timeout = self._config(tier, timeout_tier)
        identificador = f"openai_compat/{modelo}"
        json_schema = schema.model_json_schema()

        payload_schema = {
            "model": modelo,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": json_schema,
                    "strict": False,
                },
            },
        }
        try:
            dados = self._post_completions(base_url, api_key, payload_schema, timeout)
        except httpx.HTTPStatusError as erro:
            # Alguns provedores/modelos OpenAI-compat não aceitam json_schema e exigem json_object.
            if erro.response is None or erro.response.status_code not in (400, 422):
                raise
            instrucao_json = (
                f"{prompt_sistema}\n\n"
                "Responda EXCLUSIVAMENTE com um objeto JSON válido aderente ao esquema abaixo:\n"
                f"{json.dumps(json_schema, ensure_ascii=False)}"
            )
            payload_json = {
                "model": modelo,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": instrucao_json},
                    {"role": "user", "content": prompt_usuario},
                ],
                "response_format": {"type": "json_object"},
            }
            dados = self._post_completions(base_url, api_key, payload_json, timeout)

        conteudo = self._extrair_conteudo_choice(dados)
        return _validar_json_pydantic(schema, conteudo, identificador), identificador

    def invocar_texto(
        self,
        tier: str,
        prompt_sistema: str,
        prompt_usuario: str,
        temperature: float,
        timeout_tier: int,
    ) -> tuple[str, str]:
        base_url, api_key, modelo, timeout = self._config(tier, timeout_tier)
        identificador = f"openai_compat/{modelo}"
        payload = {
            "model": modelo,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
        }
        dados = self._post_completions(base_url, api_key, payload, timeout)
        texto = self._extrair_conteudo_choice(dados)
        if not texto:
            raise ValueError(f"Resposta textual vazia em '{identificador}'.")
        return texto, identificador


PROVEDORES_SECUNDARIOS: dict[str, ProvedorOllama | ProvedorOpenAICompativel] = {
    "ollama": ProvedorOllama(),
    "openai_compat": ProvedorOpenAICompativel(),
}
