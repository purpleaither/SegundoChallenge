import argparse
from pathlib import Path
import subprocess
import sys
import unittest


TEST_DIR = Path(__file__).resolve().parent
RAG_DIR = TEST_DIR.parent
PROJECT_ROOT = RAG_DIR.parents[1]
BACKEND_DIR = PROJECT_ROOT / "Back-end"
EVALUATOR = RAG_DIR / "avaliar_ragas.py"
sys.path.insert(0, str(RAG_DIR.parent))


def run_unit_tests() -> bool:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    suite.addTests(
        loader.discover(
            start_dir=str(BACKEND_DIR),
            pattern="test_*.py",
            top_level_dir=str(BACKEND_DIR),
        )
    )
    suite.addTests(
        loader.discover(
            start_dir=str(TEST_DIR),
            pattern="test_*.py",
            top_level_dir=str(TEST_DIR),
        )
    )
    if not suite.countTestCases():
        print("Nenhum teste automatizado foi encontrado.", file=sys.stderr)
        return False
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apenas-unitarios",
        action="store_true",
        help="Mantido por compatibilidade; os testes unitários são o padrão",
    )
    parser.add_argument(
        "--com-ragas",
        action="store_true",
        help="Também executa a avaliação RAGAS com um juiz local do Ollama",
    )
    parser.add_argument("--limite", type=int, help="Limita os casos da avaliação RAGAS")
    parser.add_argument(
        "--fora-do-escopo",
        action="store_true",
        help="Avalia somente as perguntas fora do escopo",
    )
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite deve ser positivo.")
    if args.fora_do_escopo and not args.com_ragas:
        parser.error("--fora-do-escopo requer --com-ragas.")
    if args.limite is not None and not args.com_ragas:
        parser.error("--limite requer --com-ragas.")

    print("Executando testes unitários...", flush=True)
    if not run_unit_tests():
        return 1
    if not args.com_ragas:
        return 0

    command = [sys.executable, str(EVALUATOR), "todos"]
    if args.limite is not None:
        command.extend(["--limite", str(args.limite)])
    if args.fora_do_escopo:
        evaluation_dir = RAG_DIR / "avaliacao"
        command.extend(
            [
                "--fora-do-escopo",
                "--amostras",
                str(evaluation_dir / "amostras_fora.jsonl"),
                "--saida",
                str(evaluation_dir / "resultados_fora"),
            ]
        )
    print("\nExecutando avaliação RAG + RAGAS com Ollama local...", flush=True)
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
