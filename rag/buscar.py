"""Protótipo de recuperação: pergunta -> trechos mais relevantes do banco vetorial."""

import re
import math
from collections import Counter
import sys
import unicodedata

import chromadb

from ingestao import COLECAO, PASTA_BASE, PASTA_DB, ler_documento

TOP_K = 4

# Fala popular -> termos dos documentos oficiais (RIA01)
SINONIMOS = {
    "mercado": "alimentos segurança alimentar cesta",
    "comida": "alimentos segurança alimentar cesta",
    "fome": "alimentos insegurança alimentar",
    "gas": "auxílio gás GLP",
    "botijao": "auxílio gás GLP",
    "luz": "energia elétrica tarifa social",
    "agua": "água esgoto tarifa social cisternas",
    "seca": "cisternas água zona rural",
    "casa": "moradia habitação Minha Casa Minha Vida",
    "aluguel": "moradia habitação",
    "remedio": "medicamentos Farmácia Popular",
    "absorvente": "dignidade menstrual absorventes",
    "idos": "pessoa idosa BPC",
    "deficien": "pessoa com deficiência BPC",
    "desempregad": "baixa renda transferência de renda Bolsa Família",
    "filhos": "família crianças Bolsa Família",
    "mae solteira": "família crianças Bolsa Família",
    "faculdade": "ensino superior Sisu cotas FIES PNAES",
    "ensino medio": "Pé-de-Meia ensino médio",
    "enem": "isenção da taxa do Enem",
    "concurso": "isenção de taxa concursos públicos",
    "onibus": "transporte interestadual passe livre",
    "internet": "chip pacote de dados Internet Brasil",
    "roca": "rural agricultura familiar fomento",
    "inss": "previdência contribuição",
    "dona de casa": "facultativo baixa renda trabalho doméstico previdência",
    "gravida": "gestantes primeira infância",
    "bebe": "primeira infância crianças",
    "negocio": "microempreendedor microcrédito",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def expandir(pergunta: str) -> str:
    p = normalizar(pergunta)
    extras = [v for chave, v in SINONIMOS.items() if re.search(rf"\b{chave}", p)
              and not (chave == "casa" and "dona de casa" in p)]
    return " ".join([pergunta, *extras])


def abrir_colecao():
    return chromadb.PersistentClient(path=str(PASTA_DB)).get_collection(COLECAO)


def buscar(colecao, pergunta: str, k: int = TOP_K) -> list[dict]:
    """Retorna os k trechos mais parecidos, com similaridade (1 - distância de cosseno)."""
    r = colecao.query(query_texts=[expandir(pergunta)], n_results=k)
    return [
        {"texto": doc, "meta": meta, "similaridade": 1 - dist}
        for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]


PALAVRAS_COMUNS = set("a o as os de da do das dos e em no na nos nas para por com um uma que tem tenho como posso meu minha filho filha filhos familia baixa renda programa programas social sociais federal federais pessoa pessoas ser nao ao sua seu pra mais algum alguma direito ajuda fazer quero preciso sobre estado outro conta comprar beneficio beneficios".split())


def termos_busca(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", normalizar(texto))
            if len(t) > 2 and t not in PALAVRAS_COMUNS]


def buscar_programas(colecao, pergunta: str, k: int = TOP_K) -> list[dict]:
    """Busca híbrida: BM25 nas fichas locais + similaridade vetorial.

    O vocabulário popular é expandido antes das duas buscas. A evidência lexical
    é registrada separadamente, sem interpretar similaridade como probabilidade.
    """
    vetoriais = buscar(colecao, pergunta, k=k * 4)
    por_arquivo = {}
    for item in vetoriais:
        por_arquivo.setdefault(item["meta"]["arquivo"], item)
    documentos = []
    for arquivo in sorted(PASTA_BASE.glob("*.md")):
        meta, corpo = ler_documento(arquivo)
        f = ficha(arquivo.name)
        # Título tem peso extra; público e benefício ajudam perguntas sem nome oficial.
        texto = " ".join([f['titulo']] * 3 + [f['resumo'], f['Tipo de benefício'], f['Público-alvo']])
        documentos.append((arquivo.name, meta, corpo, Counter(termos_busca(texto))))
    if not documentos:
        return []
    consulta = set(termos_busca(expandir(pergunta)))
    media = sum(sum(d[3].values()) for d in documentos) / len(documentos)
    frequencias = {t: sum(t in d[3] for d in documentos) for t in consulta}
    candidatos = []
    for arquivo, meta, corpo, contagem in documentos:
        tamanho = sum(contagem.values())
        score = 0.0
        for termo in consulta:
            freq = contagem[termo]
            if freq:
                idf = math.log(1 + (len(documentos) - frequencias[termo] + 0.5) / (frequencias[termo] + 0.5))
                score += idf * freq * 2.2 / (freq + 1.2 * (0.25 + 0.75 * tamanho / max(media, 1)))
        nome = set(termos_busca(meta['programa']))
        # Cobertura integral do nome oficial favorece programas identificados pela
        # expansão, sem premiar apenas palavras compartilhadas como "Bolsa".
        if nome and nome <= consulta:
            score += 8.0
        item = dict(por_arquivo.get(arquivo, {"texto": corpo, "meta": dict(meta, arquivo=arquivo), "similaridade": 0.0}))
        item['relevancia_lexical'] = score
        candidatos.append(item)
    # BM25 recupera também fichas que ficaram fora do top vetorial.
    return sorted(candidatos, key=lambda x: (x['relevancia_lexical'] + max(0, x['similaridade']) * 0.25), reverse=True)[:k]


def ficha(arquivo: str) -> dict:
    """Lê o documento do programa e devolve os campos 'Chave: valor' + o resumo de 'O que é'."""
    _, corpo = ler_documento(PASTA_BASE / arquivo)
    campos = dict(l.split(": ", 1) for l in corpo.splitlines() if ": " in l)
    campos["titulo"] = corpo.split("\n", 1)[0].lstrip("# ")
    campos["resumo"] = corpo.split("## O que é\n", 1)[1].split("\n", 1)[0]
    return campos


def resposta_natural(pergunta: str, programas: list[dict]) -> str:
    linhas = [f"Para a sua pergunta, encontrei {len(programas)} programas que podem ter relação com a sua situação:\n"]
    for i, p in enumerate(programas, 1):
        f = ficha(p["meta"]["arquivo"])
        criterios = f["Critérios"]
        if criterios.startswith("Não especificado"):
            criterios = "a base não detalha os critérios; confirme no CRAS."
        linhas.append(f"{i}. {f['titulo']}, do órgão {p['meta']['orgao']}")
        linhas.append(f"   O que é: {f['resumo']} Oferece: {f['Tipo de benefício'].rstrip('.')}.")
        linhas.append(f"   Para quem é: {f['Público-alvo']}")
        linhas.append(f"   Quem pode pedir: {criterios}")
        if f["Lei base"] != "-":
            linhas.append(f"   Lei: {f['Lei base']}")
        linhas.append("")
    linhas.append(
        "Importante: isto é só uma orientação. Quem confirma se você tem direito é o órgão "
        "responsável. Procure o CRAS mais próximo para fazer o pedido."
    )
    return "\n".join(linhas)


def main():
    args = sys.argv[1:]
    mostrar_trechos = "--trechos" in args
    usar_llm = "--llm" in args
    modelo = None
    limpos = []
    i = 0
    while i < len(args):
        if args[i] in ("--trechos", "--llm"):
            i += 1
        elif args[i] == "--modelo" and i + 1 < len(args):
            modelo = args[i + 1]
            i += 2
        else:
            limpos.append(args[i])
            i += 1

    pergunta = " ".join(limpos) or input("Pergunta: ")
    colecao = abrir_colecao()

    if usar_llm:
        from comparar import responder_rag

        resposta, _, _ = responder_rag(pergunta, colecao=colecao, modelo=modelo)
        print(resposta)
        return
    if not mostrar_trechos:
        print(resposta_natural(pergunta, buscar_programas(colecao, pergunta)))
        return
    for i, r in enumerate(buscar(colecao, pergunta), 1):
        print(f"\n[{i}] similaridade {r['similaridade']:.2f} | {r['meta']['programa']} ({r['meta']['secao']})")
        print(f"    fonte: {r['meta']['fonte']}")
        print("    " + r["texto"].replace("\n", "\n    "))


if __name__ == "__main__":
    main()
