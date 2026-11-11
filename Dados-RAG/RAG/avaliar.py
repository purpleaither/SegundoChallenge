"""Avalia buscas representativas usando o mesmo índice do assistente virtual."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from Dados.rag.rag import KnowledgeBase, ModelUnavailableError  # noqa: E402


CASES = [
    ("Estou desempregada e tenho três filhos, posso receber auxílio?", "Bolsa Família"),
    ("Tem ajuda para comprar o botijão de gás?", "Auxílio Gás"),
    ("Minha conta de luz está cara, existe desconto?", "Tarifa Social de Energia"),
    ("Minha mãe é idosa e não tem renda", "BPC"),
    ("Quero fazer faculdade mas não tenho dinheiro", "FIES Social"),
    ("Como faço para não pagar a inscrição do Enem?", "Enem"),
    ("Meu filho está no ensino médio, tem algum apoio?", "Pé-de-Meia"),
    ("Preciso de remédio de graça", "Farmácia Popular"),
    ("Onde consigo absorvente de graça?", "Dignidade Menstrual"),
    ("Moro na roça e falta água por causa da seca", "Cisternas"),
    ("Quero comprar uma casa, existe programa?", "Minha Casa"),
]


def main() -> int:
    try:
        knowledge_base = KnowledgeBase()
        hits = 0
        for question, expected_name in CASES:
            results = knowledge_base.search(question)
            found = any(
                expected_name.casefold() in result["program_name"].casefold()
                for result in results
            )
            hits += found
            best_score = 1 - results[0]["distance"] if results else 0
            print(
                f"{'OK' if found else 'ERRO'} [{best_score:.3f}] "
                f"{question} -> {[result['program_name'] for result in results]}"
            )

        print(f"\nAcerto@5: {hits}/{len(CASES)} ({hits / len(CASES):.0%})")
    except ModelUnavailableError as exc:
        print(f"Não foi possível avaliar o RAG: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
