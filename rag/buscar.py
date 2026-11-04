"""Protótipo de recuperação: pergunta -> trechos mais relevantes do banco vetorial."""

import re
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
    extras = [v for chave, v in SINONIMOS.items() if re.search(rf"\b{chave}", p)]
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


def buscar_programas(colecao, pergunta: str, k: int = TOP_K) -> list[dict]:
    """Busca mais trechos e agrupa por programa, para não repetir o mesmo programa."""
    programas = {}
    for trecho in buscar(colecao, pergunta, k=k * 4):
        programas.setdefault(trecho["meta"]["arquivo"], trecho)
    return list(programas.values())[:k]


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
    pergunta = " ".join(a for a in args if a != "--trechos") or input("Pergunta: ")
    colecao = abrir_colecao()

    if not mostrar_trechos:
        print(resposta_natural(pergunta, buscar_programas(colecao, pergunta)))
        return
    for i, r in enumerate(buscar(colecao, pergunta), 1):
        print(f"\n[{i}] similaridade {r['similaridade']:.2f} | {r['meta']['programa']} ({r['meta']['secao']})")
        print(f"    fonte: {r['meta']['fonte']}")
        print("    " + r["texto"].replace("\n", "\n    "))


if __name__ == "__main__":
    main()
