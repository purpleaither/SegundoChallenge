"""Integração do sistema multiagente com a base oficial em Dados-RAG (KnowledgeBase / ChromaDB local)."""

import re
import sys
from pathlib import Path
from typing import Optional

import chromadb

PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS_RAG = PASTA_RAIZ / "Dados-RAG"
if str(PASTA_DADOS_RAG) not in sys.path:
    sys.path.insert(0, str(PASTA_DADOS_RAG))

from RAG.dataset import build_program_chunks, read_programs, render_program_document, slug
from RAG.rag import (
    DATASET_VERSION,
    VECTOR_DB_PATH,
    KnowledgeBase,
    ModelUnavailableError,
    expand_question,
)

TOP_K = 4
LIMIAR_SIMILARIDADE = 0.25
PASTA_CHROMA_LOCAL = PASTA_RAIZ / "rag" / "chroma_db"
COLECAO_LOCAL = f"multiagente_{slug(DATASET_VERSION)}"

CAMPOS_PERFIL_BUSCA = (
    "palavras_chave_busca",
    "resumo_situacao",
    "situacao_trabalho",
    "faixa_renda_familiar_ou_per_capita",
    "composicao_familiar",
    "condicoes_especificas",
)

_PROGRAMAS_POR_ID: dict[str, dict[str, str]] | None = None
_COLECAO_FALLBACK = None


def _mapa_programas() -> dict[str, dict[str, str]]:
    """Carrega e indexa em memória os 42 programas oficiais do CSV homologado em Dados-RAG."""
    global _PROGRAMAS_POR_ID
    if _PROGRAMAS_POR_ID is None:
        _PROGRAMAS_POR_ID = {slug(row["programa"]): row for row in read_programs()}
    return _PROGRAMAS_POR_ID


def _abrir_colecao_local():
    """Abre (e indexa automaticamente na 1ª execução) o ChromaDB local sem depender de Ollama externo."""
    global _COLECAO_FALLBACK
    if _COLECAO_FALLBACK is not None:
        return _COLECAO_FALLBACK

    PASTA_CHROMA_LOCAL.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(PASTA_CHROMA_LOCAL))
    col = cliente.get_or_create_collection(
        name=COLECAO_LOCAL,
        metadata={"hnsw:space": "cosine"},
    )
    if col.count() == 0:
        chunks = build_program_chunks(list(_mapa_programas().values()))
        col.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
        )
    _COLECAO_FALLBACK = col
    return _COLECAO_FALLBACK


def _buscar_trechos_brutos(pergunta: str, k: int = TOP_K * 4) -> list[dict]:
    """Consulta KnowledgeBase (bge-m3/Ollama) se disponível; caso contrário, usa o ChromaDB local."""
    mapa = _mapa_programas()

    if VECTOR_DB_PATH.exists():
        kb = None
        try:
            kb = KnowledgeBase(path=VECTOR_DB_PATH)
            resultados_kb = kb.search(pergunta, limit=k)
            if resultados_kb:
                saida = []
                for item in resultados_kb:
                    pid = item.get("program_id") or slug(item.get("program_name", ""))
                    row = mapa.get(pid, {})
                    saida.append(
                        {
                            "texto": item["text"],
                            "similaridade": float(item["similarity"]),
                            "meta": {
                                "arquivo": pid,
                                "programa": row.get("programa") or item.get("program_name", ""),
                                "orgao": row.get("orgao_responsavel") or item.get("agency_id", ""),
                                "esfera": row.get("esfera", "Federal"),
                                "categoria": row.get("categoria", ""),
                                "fonte": row.get("fonte_documental") or item.get("title", ""),
                                "url": row.get("url_fonte") or item.get("url", ""),
                            },
                        }
                    )
                return saida
        except ModelUnavailableError:
            pass
        finally:
            if kb is not None:
                kb.close()

    col = _abrir_colecao_local()
    total = col.count()
    if total == 0:
        return []

    consulta_expandida = expand_question(pergunta)
    r = col.query(query_texts=[consulta_expandida], n_results=min(total, max(k, 4)))
    saida_local = []
    for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        pid = meta.get("program_id", "")
        row = mapa.get(pid, {})
        saida_local.append(
            {
                "texto": doc,
                "similaridade": 1.0 - float(dist),
                "meta": {
                    "arquivo": pid,
                    "programa": row.get("programa") or meta.get("program_name", ""),
                    "orgao": row.get("orgao_responsavel") or meta.get("agency_id", ""),
                    "esfera": row.get("esfera") or meta.get("jurisdiction", "Federal"),
                    "categoria": row.get("categoria", ""),
                    "fonte": row.get("fonte_documental") or meta.get("title", ""),
                    "url": row.get("url_fonte") or meta.get("url", ""),
                },
            }
        )
    return saida_local


def montar_contexto(programas: list[dict]) -> str:
    """Renderiza as fichas completas dos programas recuperados no formato documental estruturado."""
    mapa = _mapa_programas()
    blocos = []
    for i, item in enumerate(programas, 1):
        meta = item["meta"]
        pid = meta["arquivo"]
        row = mapa.get(pid)
        corpo = render_program_document(row).strip() if row else item.get("texto", "").strip()
        blocos.append(
            f"=== DOCUMENTO {i} (similaridade: {item['similaridade']:.2f}) ===\n"
            f"Programa oficial: {meta['programa']}\n"
            f"Órgão responsável: {meta['orgao']}\n"
            f"Esfera: {meta['esfera']} | Categoria: {meta['categoria']}\n"
            f"Fonte documental: {meta['fonte']}\n"
            f"URL oficial: {meta['url']}\n\n"
            f"{corpo}"
        )
    return "\n\n".join(blocos)


def violacao_operacional_p02(pergunta: str) -> bool:
    """Detecta pedidos operacionais vedados por P02 (consulta de CPF/CadÚnico, cadastro ou aprovação)."""
    p = pergunta.lower()
    tem_cpf = bool(re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", p)) or "meu cpf" in p
    acao_vedada = any(
        termo in p
        for termo in (
            "consulta aí",
            "consultar meu",
            "consulta meu",
            "consulte",
            "consultar",
            "consulta ",
            "cadunico",
            "cadúnico",
            "faz meu cadastro",
            "fazer meu cadastro",
            "fazer cadastro",
            "faz cadastro",
            "meu cadastro",
            "aprova meu",
            "aprovar",
            "foi aprovado",
            "aprovado",
        )
    )
    return tem_cpf and acao_vedada


def consultar_rag(pergunta: str, k: int = TOP_K) -> str:
    """Consulta o banco vetorial e retorna os documentos formatados."""
    por_prog: dict[str, dict] = {}
    for trecho in _buscar_trechos_brutos(pergunta, k=k * 4):
        if trecho["similaridade"] >= LIMIAR_SIMILARIDADE:
            por_prog.setdefault(trecho["meta"]["arquivo"], trecho)
    programas = list(por_prog.values())[:k]
    if not programas:
        return "Nenhum documento relevante encontrado na base."
    return montar_contexto(programas)


def montar_query_enriquecida(mensagem_usuario: str, perfil_extraido: Optional[dict] = None) -> str:
    """Combina o relato com os campos preenchidos do perfil socioeconômico."""
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


def _buscar_por_consulta(
    consulta: str,
    k_busca: int,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict[str, dict]:
    """Executa uma busca vetorial deduplicada por programa respeitando limiar e filtros opcionais."""
    melhores: dict[str, dict] = {}
    for trecho in _buscar_trechos_brutos(consulta, k=k_busca):
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
    return melhores


def recuperar_documentos_com_perfil(
    mensagem_usuario: str,
    perfil_extraido: Optional[dict] = None,
    k: int = TOP_K,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict:
    """Busca pelo relato original e pela consulta enriquecida, aplica filtros e deduplica por programa."""
    query_busca = montar_query_enriquecida(mensagem_usuario, perfil_extraido)
    consultas = list(dict.fromkeys([mensagem_usuario, query_busca]))

    melhores: dict[str, dict] = {}
    for consulta in consultas:
        parciais = _buscar_por_consulta(
            consulta,
            k_busca=k * 4,
            limiar_similaridade=limiar_similaridade,
            categoria=categoria,
            esfera=esfera,
        )
        for arquivo, trecho in parciais.items():
            atual = melhores.get(arquivo)
            if atual is None or trecho["similaridade"] > atual["similaridade"]:
                melhores[arquivo] = trecho

    programas = sorted(melhores.values(), key=lambda t: t["similaridade"], reverse=True)[:k]
    contexto = montar_contexto(programas) if programas else ""
    return {
        "query_busca": query_busca,
        "programas": programas,
        "documentos": _dividir_contexto(contexto),
        "contexto": contexto,
    }


def executar_buscas_rewoo(
    mensagem_usuario: str,
    perfil_extraido: Optional[dict],
    passos: list[dict],
    k_por_passo: int = 2,
    k_total: int = 8,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
) -> dict:
    """Executa todas as subconsultas planejadas pelo ReWOO Planner sem chamar LLM (Worker)."""
    evidencias_rewoo: dict[str, list[str]] = {}
    melhores_globais: dict[str, dict] = {}
    queries_executadas: list[str] = []

    for idx, passo in enumerate(passos or [], 1):
        id_ev = str(passo.get("id_evidencia") or f"#E{idx}").strip()
        if not id_ev.startswith("#"):
            id_ev = f"#{id_ev}"
        query_passo = str(passo.get("query_busca") or passo.get("foco_necessidade") or mensagem_usuario).strip()
        categoria = (passo.get("categoria") or "").strip() or None
        esfera = (passo.get("esfera") or "").strip() or None

        queries_executadas.append(f"{id_ev}: {query_passo}")
        parciais = _buscar_por_consulta(
            query_passo,
            k_busca=max(k_por_passo * 4, 8),
            limiar_similaridade=limiar_similaridade,
            categoria=categoria,
            esfera=esfera,
        )
        if not parciais and (categoria or esfera):
            parciais = _buscar_por_consulta(
                query_passo,
                k_busca=max(k_por_passo * 4, 8),
                limiar_similaridade=limiar_similaridade,
            )

        progs_passo = sorted(parciais.values(), key=lambda t: t["similaridade"], reverse=True)[:k_por_passo]
        ctx_passo = montar_contexto(progs_passo) if progs_passo else ""
        evidencias_rewoo[id_ev] = _dividir_contexto(ctx_passo)

        for prog in progs_passo:
            arq = prog["meta"]["arquivo"]
            atual = melhores_globais.get(arq)
            if atual is None or prog["similaridade"] > atual["similaridade"]:
                melhores_globais[arq] = prog

    if len(melhores_globais) < k_total:
        complementar = recuperar_documentos_com_perfil(
            mensagem_usuario, perfil_extraido, k=k_total, limiar_similaridade=limiar_similaridade
        )
        for prog in complementar["programas"]:
            arq = prog["meta"]["arquivo"]
            if arq not in melhores_globais:
                melhores_globais[arq] = prog

    limite_final = max(k_total, len(passos or []))
    programas_consolidados = sorted(
        melhores_globais.values(), key=lambda t: t["similaridade"], reverse=True
    )[:limite_final]
    contexto = montar_contexto(programas_consolidados) if programas_consolidados else ""

    return {
        "query_busca": " | ".join(queries_executadas) if queries_executadas else mensagem_usuario,
        "evidencias_rewoo": evidencias_rewoo,
        "programas": programas_consolidados,
        "documentos": _dividir_contexto(contexto),
        "contexto": contexto,
    }
