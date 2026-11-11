"""Executa o RAG da aplicação e avalia respostas e abstenções com RAGAS e OpenAI."""

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = Path(__file__).resolve().parent / "avaliacao"
sys.path.insert(0, str(PROJECT_ROOT))

from Dados.rag import rag  # noqa: E402
from Dados.rag.rag import KnowledgeBase, ModelUnavailableError  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler {path}: {exc}") from exc
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not {"id", "user_input", "escopo"} <= row.keys():
            raise ValueError(f"Caso inválido em {path}; esperados id, user_input e escopo.")
        if not isinstance(row["id"], str) or not row["id"].strip() or row["id"] in ids:
            raise ValueError(f"Identificador ausente ou repetido em {path}: {row['id']!r}")
        if not isinstance(row["user_input"], str) or not row["user_input"].strip():
            raise ValueError(f"Pergunta inválida no caso {row['id']}.")
        if not isinstance(row["escopo"], bool):
            raise ValueError(f"Pergunta ou campo escopo inválido no caso {row['id']}.")
        if "response" in row or "retrieved_contexts" in row:
            if not isinstance(row.get("response"), str) or not row["response"].strip():
                raise ValueError(f"Resposta inválida no caso {row['id']}.")
            if not isinstance(row.get("retrieved_contexts"), list) or any(
                not isinstance(context, str) for context in row["retrieved_contexts"]
            ):
                raise ValueError(f"Contextos recuperados inválidos no caso {row['id']}.")
        ids.add(row["id"])
    if not rows:
        raise ValueError(f"Nenhum caso encontrado em {path}.")
    return rows


def format_contexts(context: list[dict[str, Any]]) -> list[str]:
    return [
        f"Programa: {item.get('program_name', 'não informado')}\n"
        f"Órgão: {item.get('agency_id', 'não informado')}\n"
        f"Fonte: {item.get('title', 'não informada')}\n"
        f"Trecho: {item.get('text', '')}"
        for item in context
    ]


def collect(args: argparse.Namespace) -> None:
    cases = read_jsonl(args.casos)
    if args.fora_do_escopo:
        cases = [case for case in cases if not case["escopo"]]
    if args.limite:
        cases = cases[: args.limite]
    if not cases:
        raise ValueError("Não há casos para coletar com os filtros informados.")
    samples_path: Path = args.amostras
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    knowledge_base = KnowledgeBase()
    try:
        with samples_path.open("w", encoding="utf-8") as output:
            for case in cases:
                print(f"Executando RAG: {case['id']}...", flush=True)
                context = knowledge_base.search(case["user_input"])
                response = rag.generate_answer(
                    case["user_input"],
                    context,
                    [],
                    model=args.modelo,
                )
                expected_program = case.get("programa_esperado", "")
                sample = dict(
                    case,
                    response=response,
                    retrieved_contexts=format_contexts(context),
                    programas=[item.get("program_name", "") for item in context],
                    modelo_gerador=args.modelo,
                    coletado_em=datetime.now(timezone.utc).isoformat(),
                    acerto_top_k=(
                        any(expected_program.casefold() in name.casefold()
                            for name in [item.get("program_name", "") for item in context])
                        if case["escopo"] and expected_program
                        else None
                    ),
                    abstencao_correta=(
                        response == rag.OUT_OF_SCOPE_RESPONSE
                        if not case["escopo"]
                        else response != rag.OUT_OF_SCOPE_RESPONSE
                    ),
                )
                output.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
                output.flush()
    finally:
        knowledge_base.close()
    print(f"Amostras salvas em {samples_path}")


async def evaluate(args: argparse.Namespace) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Defina OPENAI_API_KEY para executar a avaliação RAGAS com a OpenAI.")
    try:
        from openai import AsyncOpenAI
        from ragas import SingleTurnSample
        from ragas.llms import llm_factory
        from ragas.metrics import AspectCritic
        from ragas.metrics.collections import (
            ContextPrecision,
            ContextRecall,
            ContextUtilization,
            Faithfulness,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Dependências de avaliação ausentes ou incompatíveis. "
            "Instale Dados/rag/requirements-avaliacao.txt."
        ) from exc

    samples = read_jsonl(args.amostras)
    args.saida.mkdir(parents=True, exist_ok=True)
    metric_names = [
        "scope_adherence",
        "faithfulness",
        "context_utilization",
        "context_precision",
        "context_recall",
    ]
    results: list[dict[str, Any]] = []
    async with AsyncOpenAI(api_key=api_key, timeout=180) as client:
        judge = llm_factory(
            args.juiz,
            client=client,
            temperature=0,
            max_tokens=args.max_tokens,
        )
        metrics = {
            "scope_adherence": AspectCritic(
                name="scope_adherence",
                definition=(
                    "Avalie a pergunta inteira e a intenção do usuário, não palavras "
                    "isoladas. Dúvidas informativas sobre benefícios e direitos sociais "
                    "devem receber orientação apoiada nos contextos, mesmo quando a pergunta "
                    "contém termos que também aparecem em assuntos cotidianos. Assuntos sem "
                    "relação com programas/direitos sociais e pedidos de consulta, cadastro "
                    "ou aprovação individual devem receber uma abstenção clara, sem tentar "
                    "atender ao pedido. Dê nota positiva somente quando a resposta adota a "
                    "conduta adequada ao escopo da pergunta."
                ),
                llm=judge,
            ),
            "faithfulness": Faithfulness(llm=judge),
            "context_utilization": ContextUtilization(llm=judge),
            "context_precision": ContextPrecision(llm=judge),
            "context_recall": ContextRecall(llm=judge),
        }
        for sample in samples:
            print(f"Avaliando {sample['id']}...", flush=True)
            row = dict(sample, modelo_juiz=args.juiz, erros={})
            row.update({name: None for name in metric_names})
            row["max_tokens_por_metrica"] = {}
            for name, metric in metrics.items():
                if name != "scope_adherence" and not sample["escopo"]:
                    continue
                if name in {"context_precision", "context_recall"} and not (
                    sample.get("reference") or ""
                ).strip():
                    continue
                inputs = {
                    "user_input": sample["user_input"],
                    "response": sample["response"],
                }
                if name != "scope_adherence":
                    inputs["retrieved_contexts"] = sample["retrieved_contexts"]
                if name in {"context_precision", "context_recall"}:
                    inputs["reference"] = sample["reference"]
                try:
                    row["max_tokens_por_metrica"][name] = args.max_tokens
                    sample_obj = SingleTurnSample(
                        user_input=inputs.get("user_input", ""),
                        response=inputs.get("response", ""),
                        retrieved_contexts=inputs.get("retrieved_contexts", []),
                        reference=inputs.get("reference", ""),
                    )

                    if hasattr(metric, "single_turn_ascore"):
                        result_metric = await metric.single_turn_ascore(sample_obj)
                        score = float(
                            result_metric.value if hasattr(result_metric, "value") else result_metric
                        )
                    elif hasattr(metric, "ascore"):
                        result_metric = await metric.ascore(**inputs)
                        score = float(
                            result_metric.value if hasattr(result_metric, "value") else result_metric
                        )
                    else:
                        raise AttributeError("Método de avaliação não encontrado.")

                except Exception as exc:
                    row["erros"][name] = str(exc)
                    print(f"  {name}: FALHOU ({exc})", flush=True)
                else:
                    if not math.isfinite(score):
                        row["erros"][name] = "A métrica retornou uma nota não finita."
                        print(f"  {name}: FALHOU (nota não finita)", flush=True)
                    else:
                        row[name] = score
                        print(f"  {name}: {score:.4f}", flush=True)
            results.append(row)
            write_jsonl(args.saida / "resultados.jsonl", results)

    summary = {"modelo_juiz": args.juiz, "amostras": len(results), "metricas": {}}
    for name in metric_names:
        scores = [row[name] for row in results if row[name] is not None]
        summary["metricas"][name] = {
            "media": sum(scores) / len(scores) if scores else None,
            "avaliadas": len(scores),
            "falhas": sum(name in row["erros"] for row in results),
        }
    for field in ("acerto_top_k", "abstencao_correta"):
        values = [row[field] for row in results if row.get(field) is not None]
        summary[field] = {
            "taxa": sum(values) / len(values) if values else None,
            "casos": len(values),
        }
    (args.saida / "resumo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fields = [
        "id",
        "user_input",
        "escopo",
        *metric_names,
        "acerto_top_k",
        "abstencao_correta",
        "erros",
    ]
    with (args.saida / "metricas.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["erros"] for row in results):
        raise RuntimeError(f"Há métricas com falha. Consulte {args.saida / 'resultados.jsonl'}.")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etapa", choices=["coletar", "avaliar", "todos"], nargs="?", default="todos")
    parser.add_argument("--casos", type=Path, default=EVALUATION_DIR / "casos.jsonl")
    parser.add_argument("--amostras", type=Path, default=EVALUATION_DIR / "amostras.jsonl")
    parser.add_argument("--saida", type=Path, default=EVALUATION_DIR / "resultados")
    parser.add_argument(
        "--modelo",
        default=rag.OPENAI_CHAT_MODEL,
        help="Modelo OpenAI usado para classificar e gerar as respostas do RAG",
    )
    parser.add_argument(
        "--juiz",
        default=rag.OPENAI_CHAT_MODEL,
        help="Modelo OpenAI usado como juiz RAGAS",
    )
    parser.add_argument("--limite", type=int, help="Executa apenas os primeiros N casos")
    parser.add_argument(
        "--fora-do-escopo",
        action="store_true",
        help="Coleta somente os casos de teste fora do escopo",
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite deve ser positivo.")
    if args.max_tokens < 1:
        parser.error("--max-tokens deve ser positivo.")
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("Defina OPENAI_API_KEY para executar o RAG e a avaliação com OpenAI.")
    try:
        if args.etapa in {"coletar", "todos"}:
            collect(args)
        if args.etapa in {"avaliar", "todos"}:
            asyncio.run(evaluate(args))
    except (OSError, ValueError, RuntimeError, ModelUnavailableError) as exc:
        parser.exit(1, f"Erro: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
