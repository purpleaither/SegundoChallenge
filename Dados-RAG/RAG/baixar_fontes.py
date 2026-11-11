"""Baixa os textos legislativos completos dos endereços oficiais da base."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from Dados.rag.dataset import read_programs  # noqa: E402
from Dados.rag.fontes import MIN_SOURCE_DOCUMENTS, download_official_sources  # noqa: E402


def main() -> int:
    try:
        available, failures = download_official_sources(read_programs())
    except (OSError, ValueError) as exc:
        print(f"Erro ao preparar fontes oficiais: {exc}", file=sys.stderr)
        return 1

    for failure in failures:
        print(f"AVISO: {failure}", file=sys.stderr)
    print(f"Documentos-fonte oficiais disponíveis: {available}.")
    if available < MIN_SOURCE_DOCUMENTS:
        print(
            f"São necessários pelo menos {MIN_SOURCE_DOCUMENTS} documentos integrais; "
            "corrija as fontes indisponíveis e tente novamente.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
