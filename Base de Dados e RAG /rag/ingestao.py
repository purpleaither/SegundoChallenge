from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = PROJECT_ROOT / "Dados" / "rag" / "base"
sys.path.insert(0, str(PROJECT_ROOT))

from Dados.rag.dataset import (  # noqa: E402
    build_official_source_chunks,
    build_program_chunks,
    read_programs,
    render_program_document,
    slug,
)
from Dados.rag.rag import (  # noqa: E402
    KnowledgeBase,
    ModelUnavailableError,
    embed_texts,
)


def write_program_documents(rows: list[dict[str, str]]) -> int:
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    documents = {
        f"{slug(row['programa'])}.md": render_program_document(row)
        for row in rows
    }

    for existing_path in BASE_PATH.glob("*.md"):
        if existing_path.name not in documents:
            existing_path.unlink()
    for filename, content in documents.items():
        (BASE_PATH / filename).write_text(content, encoding="utf-8")
    return len(documents)


def main() -> int:
    try:
        rows = read_programs()
        program_chunks = build_program_chunks(rows)
        source_chunks = build_official_source_chunks(rows)
        chunks = program_chunks + source_chunks
        embeddings: list[list[float]] = []
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset : offset + 32]
            embeddings.extend(embed_texts([chunk.text for chunk in batch]))

        knowledge_base = KnowledgeBase()
        try:
            knowledge_base.replace(chunks, embeddings)
        finally:
            knowledge_base.close()
        write_program_documents(rows)
    except (OSError, ValueError, ModelUnavailableError) as exc:
        print(f"Erro ao indexar programas sociais: {exc}", file=sys.stderr)
        return 1

    print(
        f"Programas: {len(rows)}; trechos: {len(chunks)}; "
        f"vetores: {len(embeddings)}; documentos de programas: {len(rows)}; "
        f"fontes legislativas: "
        f"{len({chunk.metadata['url'] for chunk in source_chunks})}; "
        f"trechos legislativos: {len(source_chunks)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
