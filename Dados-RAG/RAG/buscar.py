"""Demonstra a recuperação de trechos do índice usado pelo assistente virtual."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "Dados-RAG"))

from RAG.rag import KnowledgeBase, ModelUnavailableError, compose_answer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pergunta", help="Pergunta em linguagem natural")
    parser.add_argument("--top-k", type=int, default=4, help="Quantidade de programas únicos")
    parser.add_argument(
        "--responder",
        action="store_true",
        help="Gera uma resposta determinística usando os dados recuperados",
    )
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k precisa ser maior que zero.")

    knowledge_base = None
    try:
        knowledge_base = KnowledgeBase()
        results = knowledge_base.search(args.pergunta, limit=args.top_k)
        if args.responder:
            print(compose_answer(results))
            return 0
    except ModelUnavailableError as exc:
        print(f"Não foi possível consultar o RAG: {exc}", file=sys.stderr)
        return 1
    finally:
        if knowledge_base is not None:
            knowledge_base.close()

    if not results:
        print("Nenhum trecho relevante encontrado. Confira se a base já foi indexada.")
        return 0

    for index, result in enumerate(results, start=1):
        similarity = 1 - result["distance"]
        print(
            f"\n[{index}] {result['program_name']} | "
            f"{result['agency_id']} | similaridade {similarity:.3f}"
        )
        print(f"Fonte: {result['title']} (página {result['source_page'] or 'não informada'})")
        print(f"URL: {result['url']}")
        if result["legislation_url"]:
            print(f"Legislação: {result['legislation_url']}")
        print(f"Trecho: {result['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
