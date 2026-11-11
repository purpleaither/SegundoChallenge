"""Semana 3: compara LLM pura x RAG em 4 configurações e grava as métricas em resultados/.

Testes:
  T1  LLM pura            -> qwen2.5:3b responde sem nenhum contexto da base
  T2  RAG sem LLM         -> busca (MiniLM) + resposta por modelo de texto fixo (protótipo da semana 2)
  T3  RAG + LLM           -> busca (MiniLM) + qwen2.5:3b redige a resposta a partir dos trechos
  T4  RAG otimizado + LLM -> busca com embeddings multilíngues (bge-m3) + limiar de abstenção + qwen2.5:3b
  T5  combinação escolhida -> busca e abstenção do T4 + resposta por modelo de texto fixo (sem LLM)

Pré-requisitos: Ollama rodando com `qwen2.5:3b` e `bge-m3`, e `ingestao.py` já executado.
Uso (dentro de rag/):
  .venv/bin/python experimentos.py               # roda tudo
  .venv/bin/python experimentos.py --so-busca    # só as métricas de recuperação (rápido)
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

import chromadb

from avaliar import DENTRO_DO_ESCOPO, FORA_DO_ESCOPO as FORA_ORIGINAL
from buscar import TOP_K, abrir_colecao, expandir, normalizar
from ingestao import PASTA_BASE, PASTA_DB, chunkar, ler_documento

OLLAMA = "http://127.0.0.1:11434"
MODELO_LLM = "qwen2.5:3b"
MODELO_EMB = "bge-m3"
COLECAO_BGE = "beneficios_bge_m3"
PASTA_RES = Path(__file__).resolve().parent / "resultados"
SINAL_FORA = "FORA_DO_ESCOPO"

FORA_DO_ESCOPO = FORA_ORIGINAL + [
    "como eu tiro o passaporte?",
    "quanto custa um celular novo?",
]

# Nomes alternativos aceitos ao conferir se a resposta citou o programa esperado
APELIDOS = {
    "BPC": ["beneficio de prestacao continuada"],
    "Primeira Infância": ["crianca feliz"],
    "Pé-de-Meia": ["pe de meia"],
    "Distribuição de Alimentos": ["acao de distribuicao", "cesta de alimentos", "cestas de alimentos"],
    "concursos públicos": ["concurso publico"],
    "Acredita": ["acredita no primeiro passo"],
    "Tarifa Social de Energia": ["tarifa social de energia eletrica"],
    "Tarifa Social de Água": ["tarifa social de agua"],
}

PROMPT_BASE = (
    "Você é um assistente que orienta cidadãos brasileiros sobre programas sociais do governo "
    "federal. Responda em português brasileiro, com frases curtas e palavras simples, em no máximo "
    "8 linhas. Diga o nome do programa, para quem é, quem pode pedir e a lei que criou o programa "
    "(com o número). Nunca decida se a pessoa tem direito; oriente a procurar o CRAS ou o órgão "
    f"responsável. Se a pergunta não for sobre programas sociais, responda apenas: {SINAL_FORA}"
)

PROMPT_RAG = (
    PROMPT_BASE
    + "\n\nUse SOMENTE as fontes numeradas abaixo. Não invente programas, leis, valores ou critérios "
    "que não estejam nelas; se um dado não estiver nas fontes, diga que a base não informa. Cite as "
    "fontes com o número entre colchetes, por exemplo [1]. Se nenhuma fonte tiver relação com a "
    f"pergunta, responda apenas: {SINAL_FORA}\n\nFontes:\n"
)


# ---------- infraestrutura ----------

def ollama(endpoint: str, payload: dict) -> dict:
    req = Request(f"{OLLAMA}{endpoint}", data=json.dumps(payload).encode(), method="POST",
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def embed(textos: list[str]) -> list[list[float]]:
    return ollama("/api/embed", {"model": MODELO_EMB, "input": textos})["embeddings"]


def llm(sistema: str, pergunta: str) -> str:
    r = ollama("/api/chat", {
        "model": MODELO_LLM, "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": 400},
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": pergunta}],
    })
    return r["message"]["content"].strip()


def colecao_bge():
    """Indexa os mesmos 126 chunks da base com bge-m3 (uma vez) numa coleção separada."""
    cliente = chromadb.PersistentClient(path=str(PASTA_DB))
    chunks = [c for a in sorted(PASTA_BASE.glob("*.md")) for c in chunkar(a)]
    col = cliente.get_or_create_collection(COLECAO_BGE, metadata={"hnsw:space": "cosine"})
    if col.count() != len(chunks):
        cliente.delete_collection(COLECAO_BGE)
        col = cliente.create_collection(COLECAO_BGE, metadata={"hnsw:space": "cosine"})
        vetores = [v for i in range(0, len(chunks), 32)
                   for v in embed([c["texto"] for c in chunks[i:i + 32]])]
        col.add(ids=[c["id"] for c in chunks], documents=[c["texto"] for c in chunks],
                metadatas=[c["meta"] for c in chunks], embeddings=vetores)
    return col


def buscar_prog(col, pergunta: str, usar_bge: bool, expandir_q: bool = True, k: int = TOP_K):
    """Busca 4k trechos e agrupa por programa (mesma lógica de buscar.buscar_programas)."""
    q = expandir(pergunta) if expandir_q else pergunta
    if usar_bge:
        r = col.query(query_embeddings=embed([q]), n_results=k * 4)
    else:
        r = col.query(query_texts=[q], n_results=k * 4)
    progs = {}
    for meta, dist in zip(r["metadatas"][0], r["distances"][0]):
        progs.setdefault(meta["arquivo"], {"meta": meta, "similaridade": 1 - dist})
    return list(progs.values())[:k]


# ---------- métricas ----------

def norm(t: str) -> str:
    return re.sub(r"[-–]", " ", normalizar(t))


def citou_programa(resposta: str, esperado: str) -> bool:
    r = norm(resposta)
    return any(norm(n) in r for n in [esperado, *APELIDOS.get(esperado, [])])


def numero_lei(arquivo: str) -> list[str]:
    """Números das leis em 'Lei base' do documento esperado (ex.: '14.601')."""
    _, corpo = ler_documento(PASTA_BASE / arquivo)
    linha = next(l for l in corpo.splitlines() if l.startswith("Lei base:"))
    return re.findall(r"n[ºo°]\s*([\d.]+)", linha)


def arquivo_esperado(esperado: str) -> str:
    for a in sorted(PASTA_BASE.glob("*.md")):
        meta, corpo = ler_documento(a)
        if norm(esperado) in norm(meta["programa"] + " " + corpo.split("\n", 1)[0]):
            return a.name
    raise KeyError(esperado)


CORPUS = norm(" ".join(a.read_text(encoding="utf-8") for a in PASTA_BASE.glob("*.md")))
REGEX_NORMA = re.compile(r"(?:lei|decreto|portaria|medida provisoria)[^0-9\n]{0,25}?(\d{1,2}\.?\d{3})", re.I)


def normas_citadas(resposta: str) -> list[str]:
    return [m.replace(".", "") for m in REGEX_NORMA.findall(norm(resposta))]


def normas_sem_lastro(resposta: str) -> list[str]:
    """Leis/decretos citados na resposta que não aparecem em nenhum documento da base."""
    corpus = CORPUS.replace(".", "")
    return [n for n in normas_citadas(resposta) if n not in corpus]


def abstencao(resposta: str) -> bool:
    # tolera variações do modelo pequeno, como "FORA_DO_ESCOOP"
    return bool(re.search(r"fora[_ ]do[_ ]esc", norm(resposta)))


# ---------- testes ----------

def contexto(progs: list[dict]) -> str:
    blocos = []
    for i, p in enumerate(progs, 1):
        _, corpo = ler_documento(PASTA_BASE / p["meta"]["arquivo"])
        blocos.append(f"[{i}] Órgão: {p['meta']['orgao']}\n{corpo.strip()}")
    return "\n\n".join(blocos)


def avaliar_busca(col_mini, col_bge) -> dict:
    """Métricas só da recuperação: acerto@1, acerto@4, MRR e separação dentro x fora do escopo."""
    saida = {}
    for nome, col, bge in [("MiniLM", col_mini, False), ("bge-m3", col_bge, True)]:
        for exp in (False, True):
            ranks, top_dentro, top_fora = [], [], []
            for pergunta, esperado in DENTRO_DO_ESCOPO:
                progs = buscar_prog(col, pergunta, bge, exp)
                nomes = [p["meta"]["programa"] for p in progs]
                pos = next((i for i, n in enumerate(nomes, 1) if norm(esperado) in norm(n)), None)
                ranks.append(pos)
                top_dentro.append(progs[0]["similaridade"])
            for pergunta in FORA_DO_ESCOPO:
                top_fora.append(buscar_prog(col, pergunta, bge, exp)[0]["similaridade"])
            n = len(ranks)
            saida[f"{nome}{' + expansão' if exp else ''}"] = {
                "acerto@1": sum(r == 1 for r in ranks) / n,
                "acerto@4": sum(r is not None for r in ranks) / n,
                "mrr": sum(1 / r for r in ranks if r) / n,
                "menor_score_dentro": min(top_dentro),
                "maior_score_fora": max(top_fora),
                "margem": min(top_dentro) - max(top_fora),
            }
    return saida


def responder(teste: str, pergunta: str, col_mini, col_bge, limiar: float) -> dict:
    t0 = time.perf_counter()
    progs = []
    if teste == "T1":
        resp = llm(PROMPT_BASE, pergunta)
    elif teste == "T2":
        from buscar import buscar_programas, resposta_natural
        progs = buscar_programas(col_mini, pergunta)
        resp = resposta_natural(pergunta, progs)
    elif teste == "T3":
        progs = buscar_prog(col_mini, pergunta, usar_bge=False)
        resp = llm(PROMPT_RAG + contexto(progs), pergunta)
    else:  # T4 e T5 (T5 = busca do T4 + modelo de texto fixo do T2, sem LLM)
        from buscar import resposta_natural
        progs = buscar_prog(col_bge, pergunta, usar_bge=True)
        if progs[0]["similaridade"] < limiar:
            progs, resp = [], (f"{SINAL_FORA}: não encontrei esse assunto na base de programas sociais. "
                               "Procure o CRAS ou o Disque Social 121.")
        elif teste == "T5":
            resp = resposta_natural(pergunta, progs)
        else:
            resp = llm(PROMPT_RAG + contexto(progs), pergunta)
    return {"resposta": resp, "segundos": time.perf_counter() - t0,
            "recuperados": [p["meta"]["programa"] for p in progs]}


def calibrar_limiar(col_bge) -> float:
    dentro = min(buscar_prog(col_bge, p, True)[0]["similaridade"] for p, _ in DENTRO_DO_ESCOPO)
    fora = max(buscar_prog(col_bge, p, True)[0]["similaridade"] for p in FORA_DO_ESCOPO)
    return round((dentro + fora) / 2, 3) if dentro > fora else round(dentro - 0.01, 3)


def main():
    sys.stdout.reconfigure(line_buffering=True)  # mostra o progresso na hora, mesmo com "| tee"
    PASTA_RES.mkdir(exist_ok=True)
    col_mini, col_bge = abrir_colecao(), colecao_bge()

    busca = avaliar_busca(col_mini, col_bge)
    limiar = calibrar_limiar(col_bge)
    (PASTA_RES / "busca.json").write_text(json.dumps({"limiar_t4": limiar, **busca}, indent=2, ensure_ascii=False))
    print(f"== Recuperação (limiar T4 = {limiar}) ==")
    for nome, m in busca.items():
        print(f"{nome:20s} " + "  ".join(f"{k}={v:.2f}" for k, v in m.items()))
    if "--so-busca" in sys.argv:
        return

    arquivo_resumo = PASTA_RES / "resumo.json"
    resumo = json.loads(arquivo_resumo.read_text()) if arquivo_resumo.exists() else {}
    testes = [a for a in sys.argv[1:] if re.fullmatch(r"T\d", a)] or ["T1", "T2", "T3", "T4", "T5"]
    for teste in testes:
        linhas = []
        for pergunta, esperado in DENTRO_DO_ESCOPO:
            r = responder(teste, pergunta, col_mini, col_bge, limiar)
            leis = numero_lei(arquivo_esperado(esperado))
            r.update(pergunta=pergunta, esperado=esperado, escopo="dentro",
                     programa_ok=citou_programa(r["resposta"], esperado),
                     lei_esperada=leis,
                     lei_ok=bool(leis) and any(l.replace(".", "") in normas_citadas(r["resposta"]) for l in leis),
                     normas_citadas=normas_citadas(r["resposta"]),
                     normas_sem_lastro=normas_sem_lastro(r["resposta"]),
                     absteve=abstencao(r["resposta"]))
            linhas.append(r)
            print(f"{teste} {'OK ' if r['programa_ok'] else 'ERR'} {r['segundos']:5.1f}s {pergunta}")
        for pergunta in FORA_DO_ESCOPO:
            r = responder(teste, pergunta, col_mini, col_bge, limiar)
            r.update(pergunta=pergunta, escopo="fora", absteve=abstencao(r["resposta"]),
                     normas_sem_lastro=normas_sem_lastro(r["resposta"]))
            linhas.append(r)
            print(f"{teste} {'ABS' if r['absteve'] else 'RESP'} {r['segundos']:5.1f}s {pergunta}")
        (PASTA_RES / f"{teste}.json").write_text(json.dumps(linhas, indent=2, ensure_ascii=False))

        d = [l for l in linhas if l["escopo"] == "dentro"]
        f = [l for l in linhas if l["escopo"] == "fora"]
        com_lei = [l for l in d if l["lei_esperada"]]
        citam = [l for l in d if l["normas_citadas"]]
        resumo[teste] = {
            "programa_correto": sum(l["programa_ok"] for l in d) / len(d),
            "lei_correta": sum(l["lei_ok"] for l in com_lei) / len(com_lei),
            "respostas_com_norma_sem_lastro": sum(bool(l["normas_sem_lastro"]) for l in d) / len(d),
            "normas_sem_lastro_sobre_citadas": (sum(len(l["normas_sem_lastro"]) for l in citam)
                                                / max(1, sum(len(l["normas_citadas"]) for l in citam))),
            "abstencao_correta_fora": sum(l["absteve"] for l in f) / len(f),
            "abstencao_indevida_dentro": sum(l["absteve"] for l in d) / len(d),
            "latencia_media_s": sum(l["segundos"] for l in linhas) / len(linhas),
        }
    arquivo_resumo.write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print("\n== Resumo ==")
    for teste, m in resumo.items():
        print(teste, "  ".join(f"{k}={v:.2f}" for k, v in m.items()))


if __name__ == "__main__":
    main()
