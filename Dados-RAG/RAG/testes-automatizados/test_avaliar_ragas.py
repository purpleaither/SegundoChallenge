from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from Dados.rag import rag
from Dados.rag.avaliar_ragas import format_contexts, read_jsonl


class RagasEvaluationInputTests(unittest.TestCase):
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

        self.assertEqual(
            contexts,
            ["Programa: Programa X\nÓrgão: MDS\nFonte: Fonte oficial\nTrecho: Trecho"],
        )


class OpenAIChatTests(unittest.TestCase):
    def test_request_uses_openai_chat_completions_and_json_mode(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content='{"scope":"in_scope"}'))
        ]
        messages = [{"role": "user", "content": "Quais benefícios existem?"}]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI", return_value=client) as openai_client,
        ):
            answer = rag.request_openai(messages, json_object=True)

        self.assertEqual(answer, '{"scope":"in_scope"}')
        openai_client.assert_called_once_with(api_key="test-key", timeout=120)
        client.chat.completions.create.assert_called_once_with(
            model=rag.OPENAI_CHAT_MODEL,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )

    def test_request_fails_clearly_without_api_key(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(rag.ModelUnavailableError, "OPENAI_API_KEY"):
                rag.request_openai([{"role": "user", "content": "Olá"}])


if __name__ == "__main__":
    unittest.main()
