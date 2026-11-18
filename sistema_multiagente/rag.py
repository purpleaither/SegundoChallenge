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
from comparar import montar_contexto, violacao_operacional_p02 as _violacao_p02_base

colecao = abrir_colecao()


def violacao_operacional_p02(pergunta: str) -> bool:
    """Detecta pedidos operacionais vedados por P02 (consulta de CPF/CadÚnico, cadastro ou aprovação)."""
    if _violacao_p02_base(pergunta):
        return True
    p = pergunta.lower()
    tem_cpf = bool(re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", p)) or "meu cpf" in p
    acao_vedada = any(
        termo in p
        for termo in (
            "consulte",
            "consultar",
            "consulta ",
            "cadunico",
            "cadúnico",
            "fazer cadastro",
            "faz cadastro",
            "meu cadastro",
            "aprovar",
            "aprovado",
        )
    )
    return tem_cpf and acao_vedada

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


def _buscar_por_consulta(
    consulta: str,
    k_busca: int,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict[str, dict]:
    """Executa uma busca vetorial deduplicada por arquivo respeitando limiar e filtros opcionais."""
    melhores: dict[str, dict] = {}
    for trecho in buscar(colecao, consulta, k=k_busca):
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
    """Busca pelo relato original e pela consulta enriquecida, aplica filtros e deduplica por programa.

    Retorna query_busca, programas (trechos com meta/similaridade), documentos (uma ficha por
    programa) e contexto (fichas concatenadas).
    """
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
    """Executa todas as subconsultas planejadas pelo ReWOO Planner sem chamar LLM (Worker).

    Associa os documentos encontrados a cada evidência (#E1, #E2...) e consolida uma lista
    deduplicada de fichas oficiais para o Solver.
    """
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
        # Se filtros opcionais do Planner forem restritivos demais, repete sem filtro
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

    # Complementa com a busca enriquecida do perfil caso sobre espaço até k_total
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
