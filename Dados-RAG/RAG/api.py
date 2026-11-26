"""API HTTP legada GovernancIA baseada nos experimentos T5; não usada pela interface atual.

T5 = busca com embeddings bge-m3 (via Ollama) + limiar de abstenção + resposta por modelo de
texto fixo (sem LLM). Foi a melhor combinação em resultados/resumo.json.

A API ativa do assistente fica em Back-end/main.py.

Pré-requisitos: Ollama rodando com `bge-m3` e `ingestao.py` já executado.
Uso (dentro de rag/):
  .venv/bin/uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from buscar import ficha, resposta_natural
from experimentos import PASTA_RES, buscar_prog, colecao_bge

LIMIAR_PADRAO = 0.532


def carregar_limiar() -> float:
    """Usa o limiar calibrado por experimentos.py; se não existir, o último valor medido."""
    try:
        return json.loads((PASTA_RES / "busca.json").read_text())["limiar_t4"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return LIMIAR_PADRAO


LIMIAR = carregar_limiar()
MENSAGEM_FORA = (
    "Não encontrei esse assunto na base de programas sociais. "
    "Para outras dúvidas, procure o CRAS mais próximo ou ligue para o Disque Social 121."
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Monta o índice bge-m3 antes de aceitar requisições. Na primeira subida (sem chroma_db)
    # isso leva alguns minutos em CPU; depois fica salvo e a subida é imediata.
    colecao()
    yield


app = FastAPI(title="GovernancIA API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_colecao = None


def colecao():
    """Abre (e, se preciso, indexa) a coleção bge-m3. Chamada na inicialização da API."""
    global _colecao
    if _colecao is None:
        _colecao = colecao_bge()
    return _colecao


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)


class Programa(BaseModel):
    programa: str
    titulo: str
    orgao: str
    esfera: str
    categoria: str
    resumo: str
    publico_alvo: str
    criterios: str
    lei: str | None
    url: str | None
    similaridade: float


class Resposta(BaseModel):
    resposta: str
    fora_do_escopo: bool
    programas: list[Programa]


def montar_programa(p: dict) -> Programa:
    meta, f = p["meta"], ficha(p["meta"]["arquivo"])
    lei = f.get("Lei base", "-")
    return Programa(
        programa=meta["programa"],
        titulo=f["titulo"],
        orgao=meta["orgao"],
        esfera=meta["esfera"],
        categoria=meta["categoria"],
        resumo=f["resumo"],
        publico_alvo=f.get("Público-alvo", ""),
        criterios=f.get("Critérios", ""),
        lei=None if lei == "-" else lei,
        url=meta.get("url") or None,
        similaridade=round(p["similaridade"], 3),
    )


@app.get("/api/saude")
def saude():
    return {"status": "ok", "limiar": LIMIAR}


@app.post("/api/perguntar", response_model=Resposta)
def perguntar(corpo: Pergunta):
    pergunta = corpo.pergunta.strip()
    if not pergunta:
        raise HTTPException(422, "Pergunta vazia.")
    try:
        progs = buscar_prog(colecao(), pergunta, usar_bge=True)
    except OSError as erro:  # Ollama fora do ar (URLError herda de OSError)
        raise HTTPException(503, "Serviço de busca indisponível. Verifique se o Ollama está rodando.") from erro

    if not progs or progs[0]["similaridade"] < LIMIAR:
        return Resposta(resposta=MENSAGEM_FORA, fora_do_escopo=True, programas=[])
    return Resposta(
        resposta=resposta_natural(pergunta, progs),
        fora_do_escopo=False,
        programas=[montar_programa(p) for p in progs],
    )