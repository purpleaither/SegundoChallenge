from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from RAG import rag
from RAG.avaliar_ragas import (
    expected_program_rank,
    format_contexts,
    metric_inputs,
    read_jsonl,
    scope_retrieval_metrics,
)


class RagasEvaluationInputTests(unittest.TestCase):
    def test_expected_program_rank_distinguishes_top_one_from_top_k(self) -> None:
        self.assertEqual(
            expected_program_rank("Bolsa Família", ["BPC", "Bolsa Família"]),
            2,
        )
        self.assertIsNone(expected_program_rank("Bolsa Família", ["BPC"]))

    def test_scope_metrics_separate_abstention_from_in_scope_coverage(self) -> None:
        self.assertEqual(
            scope_retrieval_metrics(in_scope=True, has_context=True),
            {
                "abstencao_correta": None,
                "resposta_com_contexto_em_escopo": True,
                "decisao_escopo_correta": True,
            },
        )
        self.assertEqual(
            scope_retrieval_metrics(in_scope=False, has_context=False),
            {
                "abstencao_correta": True,
                "resposta_com_contexto_em_escopo": None,
                "decisao_escopo_correta": True,
            },
        )

    def test_read_jsonl_validates_required_case_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "casos.jsonl"
            path.write_text(
                json.dumps(
                    {"id": "caso-1", "user_input": "Como pedir o benefício?", "escopo": True}
                ),
                encoding="utf-8",
            )

            rows = read_jsonl(path)

        self.assertEqual(rows[0]["id"], "caso-1")

    def test_read_jsonl_rejects_non_string_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "amostras.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "id": "caso-1",
                        "user_input": "Como pedir o benefício?",
                        "escopo": True,
                        "response": "Consulte a fonte [1].",
                        "retrieved_contexts": [None],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Contextos recuperados inválidos"):
                read_jsonl(path)

    def test_format_contexts_preserves_program_and_source(self) -> None:
        contexts = format_contexts(
            [{"program_name": "Programa X", "agency_id": "MDS", "title": "Fonte oficial", "text": "Trecho"}]
        )

        self.assertIn("Programa: Programa X", contexts[0])
        self.assertIn("Órgão responsável: MDS", contexts[0])
        self.assertIn("Fonte: Fonte oficial", contexts[0])
        self.assertIn("Trecho recuperado: Trecho", contexts[0])

    def test_context_precision_and_recall_receive_only_supported_fields(self) -> None:
        inputs = metric_inputs(
            "context_precision",
            "Pergunta",
            "Resposta",
            ["Contexto"],
            "Referência",
        )

        self.assertEqual(
            inputs,
            {
                "user_input": "Pergunta",
                "retrieved_contexts": ["Contexto"],
                "reference": "Referência",
            },
        )

    def test_faithfulness_receives_the_response_and_retrieved_context(self) -> None:
        inputs = metric_inputs(
            "faithfulness",
            "Pergunta",
            "Resposta",
            ["Contexto"],
        )

        self.assertEqual(
            inputs,
            {
                "user_input": "Pergunta",
                "response": "Resposta",
                "retrieved_contexts": ["Contexto"],
            },
        )


class LocalEvaluationConfigTests(unittest.TestCase):
    def test_ragas_judge_defaults_to_local_ollama_model(self) -> None:
        self.assertTrue(rag.OLLAMA_EVALUATION_MODEL)
        self.assertTrue(rag.OLLAMA_URL.startswith("http://127.0.0.1:"))


if __name__ == "__main__":
    unittest.main()
