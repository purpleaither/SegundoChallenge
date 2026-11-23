"""Pipeline de ingestão: CSV -> documentos curados (base/) -> chunks -> embeddings -> ChromaDB."""

import csv
import re
import shutil
import unicodedata
from pathlib import Path

import chromadb

AQUI = Path(__file__).resolve().parent
CSV = AQUI.parent / "Base de Dados e RAG " / "programas_sociais_legislacao_links_oficiais.csv"  # a pasta termina com espaço
PASTA_BASE = AQUI / "base"
PASTA_DB = AQUI / "chroma_db"
COLECAO = "beneficios"


def slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:60]


def ou(valor: str, padrao: str = "Não especificado no documento de origem.") -> str:
    return valor.strip() or padrao


def gerar_documentos() -> list[Path]:
    """Etapa 1: cada linha do CSV vira um documento Markdown com 3 seções."""
    # Lê o CSV antes de apagar a base: se o arquivo faltar, base/ continua intacta
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    shutil.rmtree(PASTA_BASE, ignore_errors=True)
    PASTA_BASE.mkdir()
    arquivos = []
    for r in linhas:
        nome = r["programa"]
        if r["nome_atual_encontrado_2026"]:
            nome += f" (nome atual: {r['nome_atual_encontrado_2026']})"
        texto = f"""---
programa: {r['programa']}
orgao: {r['orgao_responsavel']}
esfera: {r['esfera']}
categoria: {r['categoria']}
fonte: {r['fonte_documental']}, p. {r['pagina_fonte_pdf']}
url: {r['url_fonte_legislacao'] or r['url_fonte']}
---
# {nome}

## O que é
{r['descricao_categoria']}
Tipo de benefício: {r['tipo_beneficio']}
Órgão responsável: {r['orgao_responsavel']}

## Quem pode
Público-alvo: {ou(r['descricao_publico_alvo'])}
Critérios: {ou(r['criterios_elegibilidade_resumidos'])}
Situação do critério: {r['status_criterio']}.

## Legislação
Lei base: {ou(r['legislacao_base'], '-')}
Regulamentação: {ou(r['regulamentacao_principal'], '-')}
Atualização recente: {ou(r['atualizacao_normativa_recente'], '-')}
Observações: {ou(r['observacoes_legislacao'], '-')}
"""
        arquivo = PASTA_BASE / f"{slug(r['programa'])}.md"
        arquivo.write_text(texto, encoding="utf-8")
        arquivos.append(arquivo)
    return arquivos


def ler_documento(arquivo: Path) -> tuple[dict, str]:
    _, cabecalho, corpo = arquivo.read_text(encoding="utf-8").split("---\n", 2)
    meta = dict(linha.split(": ", 1) for linha in cabecalho.strip().splitlines())
    return meta, corpo


def chunkar(arquivo: Path) -> list[dict]:
    """Etapa 2: um chunk por seção '##', com o nome do programa no início para dar contexto."""
    meta, corpo = ler_documento(arquivo)
    titulo = corpo.split("\n", 1)[0].lstrip("# ").strip()
    chunks = []
    for secao in re.split(r"\n## ", corpo)[1:]:
        nome_secao, conteudo = secao.split("\n", 1)
        chunks.append({
            "id": f"{arquivo.stem}#{slug(nome_secao)}",
            "texto": f"{titulo} - {nome_secao}\n{conteudo.strip()}",
            "meta": {**meta, "secao": nome_secao, "arquivo": arquivo.name},
        })
    return chunks


def indexar(chunks: list[dict]):
    """Etapas 3 e 4: o Chroma gera os embeddings (all-MiniLM-L6-v2) e grava em chroma_db/."""
    cliente = chromadb.PersistentClient(path=str(PASTA_DB))
    if COLECAO in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(COLECAO)
    colecao = cliente.create_collection(COLECAO, metadata={"hnsw:space": "cosine"})
    colecao.add(
        ids=[c["id"] for c in chunks],
        documents=[c["texto"] for c in chunks],
        metadatas=[c["meta"] for c in chunks],
    )
    return colecao


def main():
    arquivos = gerar_documentos()
    chunks = [c for a in arquivos for c in chunkar(a)]
    colecao = indexar(chunks)
    print(f"{len(arquivos)} documentos -> {len(chunks)} chunks -> {colecao.count()} vetores em {PASTA_DB.name}/")


if __name__ == "__main__":
    main()
