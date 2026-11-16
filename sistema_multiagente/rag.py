import re
import sys
from pathlib import Path
from typing import Optional

# 1. Adiciona a pasta ../rag ao caminho do Python para importar o RAG existente
PASTA_RAG = Path(__file__).resolve().parent.parent / "rag"
if str(PASTA_RAG) not in sys.path:
    sys.path.insert(0, str(PASTA_RAG))

# 2. Importa os recursos do RAG e abre a conexão com o banco vetorial (ChromaDB)
from buscar import TOP_K, abrir_colecao, buscar, buscar_programas
from comparar import montar_contexto, violacao_operacional_p02

colecao = abrir_colecao()

LIMIAR_SIMILARIDADE = 0.25
CAMPOS_PERFIL_BUSCA = (
    "palavras_chave_busca",
    "resumo_situacao",
    "situacao_trabalho",
    "faixa_renda_familiar_ou_per_capita",
    "composicao_familiar",
    "condicoes_especificas",
)


# 3. Consulta o banco vetorial e retorna os documentos formatados para o agente
def consultar_rag(pergunta: str, k: int = TOP_K) -> str:
    programas = buscar_programas(colecao, pergunta, k=k)
    if not programas:
        return "Nenhum documento relevante encontrado na base."
    return montar_contexto(programas)


def montar_query_enriquecida(mensagem_usuario: str, perfil_extraido: Optional[dict] = None) -> str:
    """Combina o relato com os campos preenchidos do perfil.

    As palavras-chave vêm primeiro porque o all-MiniLM-L6-v2 trunca textos longos e o
    `expandir()` de rag/buscar.py acrescenta os sinônimos RIA01 ao final da consulta.
    """
    partes = []
    for campo in CAMPOS_PERFIL_BUSCA:
        valor = (perfil_extraido or {}).get(campo)
        if isinstance(valor, list):
            partes.extend(str(v) for v in valor if v)
        elif valor:
            partes.append(str(valor))
    partes.append(mensagem_usuario)
    return " ".join(dict.fromkeys(p.strip() for p in partes if p and p.strip()))


def _dividir_contexto(contexto: str) -> list[str]:
    """Separa o texto de montar_contexto() em uma ficha por programa ('=== DOCUMENTO N ...')."""
    return [bloco.strip() for bloco in re.split(r"(?m)^(?==== DOCUMENTO \d+)", contexto) if bloco.strip()]


def recuperar_documentos_com_perfil(
    mensagem_usuario: str,
    perfil_extraido: Optional[dict] = None,
    k: int = TOP_K,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict:
    """Busca pelo relato original e pela consulta enriquecida, aplica filtros e deduplica por programa.

    Retorna query_busca, programas (trechos com meta/similaridade), documentos (uma ficha por
    programa) e contexto (fichas concatenadas).
    """
    query_busca = montar_query_enriquecida(mensagem_usuario, perfil_extraido)
    consultas = list(dict.fromkeys([mensagem_usuario, query_busca]))

    melhores: dict[str, dict] = {}
    for consulta in consultas:
        for trecho in buscar(colecao, consulta, k=k * 4):
            meta = trecho["meta"]
            if trecho["similaridade"] < limiar_similaridade:
                continue
            if categoria and meta.get("categoria", "").lower() != categoria.lower():
                continue
            if esfera and meta.get("esfera", "").lower() != esfera.lower():
                continue
            atual = melhores.get(meta["arquivo"])
            if atual is None or trecho["similaridade"] > atual["similaridade"]:
                melhores[meta["arquivo"]] = trecho

    programas = sorted(melhores.values(), key=lambda t: t["similaridade"], reverse=True)[:k]
    contexto = montar_contexto(programas) if programas else ""
    return {
        "query_busca": query_busca,
        "programas": programas,
        "documentos": _dividir_contexto(contexto),
        "contexto": contexto,
    }
