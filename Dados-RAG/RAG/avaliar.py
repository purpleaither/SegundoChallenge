"""Mede recuperação@4 e abstenção no conjunto versionado de perguntas."""

import json
import sys
from pathlib import Path
from typing import Any


RAG_ROOT = Path(__file__).resolve().parent
CASE_PATH = RAG_ROOT / "avaliacao" / "casos.jsonl"
sys.path.insert(0, str(RAG_ROOT.parent))

from RAG.rag import KnowledgeBase, ModelUnavailableError  # noqa: E402


def read_cases(path: Path = CASE_PATH) -> list[dict[str, Any]]:
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler os casos de avaliação: {exc}") from exc
    if not rows or any(
        not isinstance(row, dict)
        or not isinstance(row.get("user_input"), str)
        or not isinstance(row.get("escopo"), bool)
        for row in rows
    ):
        raise ValueError(f"O conjunto de casos está vazio ou inválido: {path}")
    return rows


def main() -> int:
    try:
        cases = read_cases()
        knowledge_base = KnowledgeBase()
        try:
            relevant_cases = 0
            top_1_hits = 0
            top_4_hits = 0
            reciprocal_ranks = []
            out_of_scope_cases = 0
            correct_abstentions = 0
            for case in cases:
                results = knowledge_base.search(case["user_input"], limit=4)
                names = [result["program_name"] for result in results]
                expected = case.get("programa_esperado", "")
                if case["escopo"]:
                    relevant_cases += 1
                    rank = next(
                        (
                            index
                            for index, name in enumerate(names, start=1)
                            if expected and expected.casefold() in name.casefold()
                        ),
                        None,
                    )
                    top_1_hits += rank == 1
                    top_4_hits += rank is not None
                    reciprocal_ranks.append(1 / rank if rank is not None else 0)
                    status = f"RANK {rank}" if rank is not None else "ERRO"
                else:
                    out_of_scope_cases += 1
                    found = not results
                    correct_abstentions += found
                    status = "ABSTÉM" if found else "RESULTADO"
                print(f"{status} {case['user_input']} -> {names}")
        finally:
            knowledge_base.close()
    except (OSError, ValueError, ModelUnavailableError) as exc:
        print(f"Não foi possível avaliar o RAG: {exc}", file=sys.stderr)
        return 1

    top_1_rate = top_1_hits / relevant_cases if relevant_cases else 0
    top_4_rate = top_4_hits / relevant_cases if relevant_cases else 0
    mrr = sum(reciprocal_ranks) / relevant_cases if relevant_cases else 0
    abstention_rate = correct_abstentions / out_of_scope_cases if out_of_scope_cases else 0
    print(f"\nAcerto@1: {top_1_hits}/{relevant_cases} ({top_1_rate:.0%})")
    print(f"Acerto@4: {top_4_hits}/{relevant_cases} ({top_4_rate:.0%})")
    print(f"MRR: {mrr:.3f}")
    print(
        "Abstenção correta fora do escopo: "
        f"{correct_abstentions}/{out_of_scope_cases} ({abstention_rate:.0%})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
