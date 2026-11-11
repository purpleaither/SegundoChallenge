from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

from .fontes import MIN_SOURCE_DOCUMENTS, SOURCE_DOCUMENTS_PATH, read_source_documents
from .rag import DATASET_VERSION, SourceChunk, chunk_text, is_official_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "Dados" / "programas_sociais_legislacao_links_oficiais.csv"
REQUIRED_COLUMNS = {
    "programa",
    "esfera",
    "categoria",
    "descricao_categoria",
    "tipo_beneficio",
    "descricao_publico_alvo",
    "criterios_elegibilidade_resumidos",
    "orgao_responsavel",
    "status_criterio",
    "fonte_documental",
    "pagina_fonte_pdf",
    "url_fonte",
    "data_documento",
    "nome_atual_encontrado_2026",
    "legislacao_base",
    "regulamentacao_principal",
    "atualizacao_normativa_recente",
    "tipo_referencia_legislativa",
    "observacoes_validacao",
    "observacoes_legislacao",
    "url_fonte_legislacao",
    "data_pesquisa_legislacao",
}


def slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:60]


def read_programs(path: Path = CSV_PATH) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    columns = {column.strip() for column in reader.fieldnames or []}
    missing_columns = REQUIRED_COLUMNS - columns
    if missing_columns:
        raise ValueError(
            "O CSV não contém as colunas obrigatórias: "
            + ", ".join(sorted(missing_columns))
        )

    programs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row_number, raw_row in enumerate(reader, start=2):
        if None in raw_row or any(
            value is not None and not isinstance(value, str)
            for value in raw_row.values()
        ):
            raise ValueError(f"A linha {row_number} tem uma quantidade inválida de colunas.")
        if not any((value or "").strip() for value in raw_row.values()):
            continue
        row = {
            (key or "").strip(): (value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        name = row.get("programa", "")
        if not name:
            raise ValueError(f"O programa na linha {row_number} não tem nome.")
        program_id = slug(name)
        if not program_id or program_id in seen_ids:
            raise ValueError(f"Nome de programa vazio ou duplicado na linha {row_number}.")
        seen_ids.add(program_id)

        for field in (
            "esfera",
            "categoria",
            "descricao_categoria",
            "tipo_beneficio",
            "orgao_responsavel",
            "status_criterio",
            "fonte_documental",
        ):
            if not row.get(field):
                raise ValueError(f"O campo '{field}' está vazio na linha {row_number}.")
        if not is_official_url(row["url_fonte"]):
            raise ValueError(
                f"A fonte principal do programa '{name}' precisa usar HTTPS em domínio oficial."
            )
        legal_url = row.get("url_fonte_legislacao", "")
        if legal_url and not is_official_url(legal_url):
            raise ValueError(
                f"A fonte legislativa do programa '{name}' precisa usar HTTPS em domínio oficial."
            )
        programs.append(row)

    if not programs:
        raise ValueError("O CSV não contém programas para indexar.")
    return programs


def program_as_api_record(row: dict[str, str]) -> dict[str, Any]:
    criteria = row["criterios_elegibilidade_resumidos"]
    return {
        "id": slug(row["programa"]),
        "agency_id": row["orgao_responsavel"],
        "name": row["programa"],
        "current_name": row["nome_atual_encontrado_2026"],
        "summary": row["descricao_categoria"],
        "category": row["categoria"],
        "benefit_type": row["tipo_beneficio"],
        "audience": row["descricao_publico_alvo"],
        "criteria": [criteria] if criteria else [],
        "criteria_status": row["status_criterio"],
        "source_title": row["fonte_documental"],
        "source_page": row["pagina_fonte_pdf"],
        "source_url": row["url_fonte"],
        "legislation_base": row["legislacao_base"],
        "regulation": row["regulamentacao_principal"],
        "recent_update": row["atualizacao_normativa_recente"],
        "legislation_reference_type": row["tipo_referencia_legislativa"],
        "validation_notes": row["observacoes_validacao"],
        "legislation_notes": row["observacoes_legislacao"],
        "legislation_url": row["url_fonte_legislacao"],
        "research_date": row["data_pesquisa_legislacao"],
        "source_date": row["data_documento"],
        "scope": row["esfera"],
    }


def render_program_document(row: dict[str, str]) -> str:
    name = row["programa"]
    current_name = row["nome_atual_encontrado_2026"]
    return f"""# {name}

## Sobre o programa
Nome atual indicado na planilha: {current_name or "Não informado"}
Abrangência: {row["esfera"]}
Categoria: {row["categoria"]}
Descrição: {row["descricao_categoria"]}
Tipo de benefício: {row["tipo_beneficio"]}
Órgão responsável: {row["orgao_responsavel"]}

## Público e critérios
Público-alvo: {row["descricao_publico_alvo"] or "Não especificado no documento de origem."}
Critérios: {row["criterios_elegibilidade_resumidos"] or "Não especificados no documento de origem."}
Status dos critérios no documento: {row["status_criterio"]}

## Legislação
Legislação base: {row["legislacao_base"] or "Não informada"}
Regulamentação principal: {row["regulamentacao_principal"] or "Não informada"}
Atualização normativa recente: {row["atualizacao_normativa_recente"] or "Não informada"}
Tipo de referência legislativa: {row["tipo_referencia_legislativa"] or "Não informado"}
Observações: {row["observacoes_legislacao"] or "Nenhuma observação informada."}
Observações de validação: {row["observacoes_validacao"] or "Nenhuma observação informada."}

## Fontes
Documento de origem: {row["fonte_documental"]}
Página: {row["pagina_fonte_pdf"] or "Não informada"}
Data do documento: {row["data_documento"] or "Não informada"}
URL da fonte principal: {row["url_fonte"]}
URL da legislação: {row["url_fonte_legislacao"] or "Não informada"}
Data da pesquisa legislativa: {row["data_pesquisa_legislacao"] or "Não informada"}
"""


def build_program_chunks(rows: list[dict[str, str]]) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for row in rows:
        program_id = slug(row["programa"])
        metadata = {
            "dataset_version": DATASET_VERSION,
            "program_id": program_id,
            "program_name": row["programa"],
            "agency_id": row["orgao_responsavel"],
            "title": row["fonte_documental"],
            "url": row["url_fonte"],
            "legislation_url": row["url_fonte_legislacao"],
            "source_page": row["pagina_fonte_pdf"],
            "source_date": row["data_documento"],
            "researched_at": row["data_pesquisa_legislacao"],
            "criteria_status": row["status_criterio"],
            "legislation_reference_type": row["tipo_referencia_legislativa"],
            "validation_notes": row["observacoes_validacao"],
            "region": "DF",
            "jurisdiction": row["esfera"],
        }
        document = render_program_document(row)
        title = document.splitlines()[0].removeprefix("# ").strip()
        for section in re.split(r"\n## ", document)[1:]:
            section_name, content = section.split("\n", 1)
            section_text = f"{title} - {section_name}\n{content.strip()}"
            for index, chunk in enumerate(chunk_text(section_text)):
                chunks.append(
                    SourceChunk(
                        id=f"{program_id}-{slug(section_name)}-{index:03d}",
                        text=chunk,
                        metadata={**metadata, "section": section_name},
                    )
                )
    return chunks


def build_official_source_chunks(
    rows: list[dict[str, str]],
    source_dir: Path = SOURCE_DOCUMENTS_PATH,
) -> list[SourceChunk]:
    rows_by_url: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        url = row.get("url_fonte_legislacao", "").strip()
        if url:
            rows_by_url.setdefault(url, []).append(row)

    documents = [
        document
        for document in read_source_documents(source_dir)
        if document.url in rows_by_url
    ]
    if len(documents) < MIN_SOURCE_DOCUMENTS:
        raise ValueError(
            f"Foram encontrados {len(documents)} documentos-fonte oficiais; "
            f"são necessários pelo menos {MIN_SOURCE_DOCUMENTS}."
        )

    chunks: list[SourceChunk] = []
    for document in documents:
        document_hash = hashlib.sha256(document.url.encode("utf-8")).hexdigest()[:16]
        for row in rows_by_url[document.url]:
            program_id = slug(row["programa"])
            content = f"{row['programa']} - {document.title}\n\n{document.text}"
            metadata = {
                "dataset_version": DATASET_VERSION,
                "program_id": program_id,
                "program_name": row["programa"],
                "agency_id": row["orgao_responsavel"],
                "title": document.title,
                "url": document.url,
                "legislation_url": document.url,
                "source_page": "",
                "source_date": "",
                "researched_at": document.retrieved_at,
                "criteria_status": row["status_criterio"],
                "legislation_reference_type": row["tipo_referencia_legislativa"],
                "validation_notes": row["observacoes_validacao"],
                "region": "DF",
                "jurisdiction": row["esfera"],
                "section": "Texto integral da legislação",
                "source_kind": "legislation",
            }
            for index, chunk in enumerate(chunk_text(content)):
                chunks.append(
                    SourceChunk(
                        id=f"legislation-{document_hash}-{program_id}-{index:03d}",
                        text=chunk,
                        metadata=metadata,
                    )
                )
    return chunks
