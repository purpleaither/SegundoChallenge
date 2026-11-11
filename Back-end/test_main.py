from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

import main
from Dados.rag.rag import ModelUnavailableError


class StubKnowledgeBase:
    def __init__(self, results=None, error=None) -> None:
        self.results = results or []
        self.error = error
        self.last_question = ""

    def search(self, _question: str) -> list[dict]:
        self.last_question = _question
        if self.error is not None:
            raise self.error
        return self.results


class ApiDataTests(unittest.TestCase):
    def test_api_lists_programs_from_the_new_csv(self) -> None:
        programs = main.list_benefits(agency_id=None)
        bpc = next(program for program in programs if program.id == "beneficio-de-prestacao-continuada-bpc")

        self.assertEqual(len(programs), 42)
        self.assertIn("MDS", bpc.source_title)
        self.assertEqual(bpc.source_page, "2")
        self.assertTrue(bpc.source_url.startswith("https://"))
        self.assertTrue(bpc.legislation_url.startswith("https://"))
        self.assertEqual(bpc.criteria_status, "Informação parcial no documento")

    def test_api_filters_programs_by_their_responsible_agency(self) -> None:
        programs = main.list_benefits(agency_id="MDS")

        self.assertTrue(programs)
        self.assertTrue(all(program.agency_id == "MDS" for program in programs))

    def test_api_surfaces_csv_errors_instead_of_using_an_old_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "programas.csv"
            data_path.write_text("invalid,csv\nrow,value\n", encoding="utf-8")

            with patch.object(main, "CSV_PATH", data_path):
                with self.assertRaises(HTTPException) as error:
                    main.load_programs()

        self.assertEqual(error.exception.status_code, 500)

    def test_assistant_does_not_suggest_unreviewed_benefits(self) -> None:
        response = main.ask_assistant(main.AssistantRequest(question="Cartão Prato Cheio"))

        self.assertEqual(response.benefits, [])
        self.assertIn("não significa que você não tenha direito", response.answer)

    def test_assistant_finds_a_program_and_keeps_source_limitations(self) -> None:
        response = main.ask_assistant(
            main.AssistantRequest(question="Quais critérios para o BPC?")
        )

        bpc = next(
            benefit
            for benefit in response.benefits
            if benefit.id == "beneficio-de-prestacao-continuada-bpc"
        )
        self.assertEqual(bpc.criteria_status, "Informação parcial no documento")

    def test_audio_limit_resets_by_conversation_and_blocks_the_eleventh_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(
                main,
                "AUDIO_LIMIT_DB",
                Path(temporary_directory) / "audio.sqlite3",
            ):
                conversation_id = uuid4()
                for expected_used in range(1, main.AUDIO_LIMIT + 1):
                    quota = main.reserve_audio_turn(conversation_id)
                    self.assertEqual(quota.used, expected_used)

                with self.assertRaises(HTTPException) as error:
                    main.reserve_audio_turn(conversation_id)
                untouched_conversation = main.audio_quota(uuid4())

        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(untouched_conversation.remaining, main.AUDIO_LIMIT)

    def test_audio_reservation_can_only_be_used_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(
                main,
                "AUDIO_LIMIT_DB",
                Path(temporary_directory) / "audio.sqlite3",
            ):
                conversation_id = uuid4()
                reservation = main.reserve_audio_turn(conversation_id)
                main.consume_audio_reservation(conversation_id, reservation.reservation_id)

                with self.assertRaises(HTTPException) as error:
                    main.consume_audio_reservation(conversation_id, reservation.reservation_id)

        self.assertEqual(error.exception.status_code, 409)

    def test_audio_quota_resets_after_24_hours(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "audio.sqlite3"
            with patch.object(main, "AUDIO_LIMIT_DB", data_path):
                conversation_id = uuid4()
                main.reserve_audio_turn(conversation_id)
                previous_window = (
                    datetime.now(timezone.utc) - timedelta(hours=24, seconds=1)
                ).isoformat()
                with closing(sqlite3.connect(data_path)) as connection:
                    with connection:
                        connection.execute(
                            """
                            UPDATE conversation_audio_limits
                            SET window_started_at = ?
                            WHERE conversation_id = ?
                            """,
                            (previous_window, str(conversation_id)),
                        )

                quota = main.audio_quota(conversation_id)
                renewed_reservation = main.reserve_audio_turn(conversation_id)

        self.assertEqual(quota.remaining, main.AUDIO_LIMIT)
        self.assertEqual(renewed_reservation.used, 1)

    def test_chat_uses_retrieved_official_sources_and_returns_citations(self) -> None:
        source = {
            "agency_id": "SEDES",
            "title": "Página oficial",
            "url": "https://www.gov.br/exemplo",
            "legislation_url": "",
            "source_page": "2",
            "source_date": "2025-04",
            "researched_at": "2026-10-31",
            "text": "Orientação oficial revisada.",
        }
        knowledge_base = StubKnowledgeBase(results=[source])
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(
                    main,
                    "AUDIO_LIMIT_DB",
                    Path(temporary_directory) / "audio.sqlite3",
                ),
                patch.object(main, "get_knowledge_base", return_value=knowledge_base),
                patch.object(
                    main,
                    "generate_answer",
                    return_value="Resposta baseada na fonte [1].",
                ),
            ):
                response = main.chat(
                    main.ChatRequest(
                        conversation_id=uuid4(),
                        question="Como buscar atendimento?",
                    )
                )

        self.assertEqual(response.answer, "Resposta baseada na fonte [1].")
        self.assertEqual(response.citations[0]["url"], source["url"])

    def test_chat_classifies_questions_even_when_search_returns_no_context(self) -> None:
        knowledge_base = StubKnowledgeBase()
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(
                    main,
                    "AUDIO_LIMIT_DB",
                    Path(temporary_directory) / "audio.sqlite3",
                ),
                patch.object(main, "get_knowledge_base", return_value=knowledge_base),
                patch.object(
                    main,
                    "generate_answer",
                    return_value="Este assistente orienta somente sobre programas sociais.",
                ) as generate,
            ):
                response = main.chat(
                    main.ChatRequest(
                        conversation_id=uuid4(),
                        question="Qual é o melhor filme de terror?",
                    )
                )

        generate.assert_called_once_with(
            "Qual é o melhor filme de terror?",
            [],
            [],
        )
        self.assertEqual(response.citations, [])
        self.assertEqual(
            response.notice,
            "Não foram usadas fontes recuperadas da base para esta resposta.",
        )

    def test_chat_does_not_cite_retrieved_documents_after_scope_abstention(self) -> None:
        source = {
            "agency_id": "MDS",
            "title": "Página oficial",
            "url": "https://www.gov.br/exemplo",
            "legislation_url": "",
            "source_page": "",
            "source_date": "",
            "researched_at": "",
            "text": "Trecho sem relação com a pergunta.",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(
                    main,
                    "AUDIO_LIMIT_DB",
                    Path(temporary_directory) / "audio.sqlite3",
                ),
                patch.object(
                    main,
                    "get_knowledge_base",
                    return_value=StubKnowledgeBase(results=[source]),
                ),
                patch.object(
                    main,
                    "generate_answer",
                    return_value=main.OUT_OF_SCOPE_RESPONSE,
                ),
            ):
                response = main.chat(
                    main.ChatRequest(
                        conversation_id=uuid4(),
                        question="Como faço bolo de cenoura no fogão a gás?",
                    )
                )

        self.assertEqual(response.answer, main.OUT_OF_SCOPE_RESPONSE)
        self.assertEqual(response.citations, [])

    def test_chat_reports_local_model_unavailability(self) -> None:
        knowledge_base = StubKnowledgeBase(error=ModelUnavailableError("Ollama indisponível."))
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(
                    main,
                    "AUDIO_LIMIT_DB",
                    Path(temporary_directory) / "audio.sqlite3",
                ),
                patch.object(main, "get_knowledge_base", return_value=knowledge_base),
            ):
                with self.assertRaises(HTTPException) as error:
                    main.chat(
                        main.ChatRequest(
                            conversation_id=uuid4(),
                            question="Quais documentos são necessários?",
                        )
                    )

        self.assertEqual(error.exception.status_code, 503)

    def test_voice_chat_requires_and_consumes_a_reserved_audio_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(
                main,
                "AUDIO_LIMIT_DB",
                Path(temporary_directory) / "audio.sqlite3",
            ):
                conversation_id = uuid4()
                reservation = main.reserve_audio_turn(conversation_id)
                knowledge_base = StubKnowledgeBase()
                with (
                    patch.object(main, "get_knowledge_base", return_value=knowledge_base),
                    patch.object(
                        main,
                        "generate_answer",
                        return_value="Ainda não encontrei um trecho correspondente.",
                    ),
                ):
                    response = main.chat(
                        main.ChatRequest(
                            conversation_id=conversation_id,
                            question="Quero saber sobre atendimento.",
                            input_mode="voice",
                            audio_reservation_id=reservation.reservation_id,
                        )
                    )

                with self.assertRaises(HTTPException) as error:
                    with patch.object(main, "get_knowledge_base", return_value=knowledge_base):
                        main.chat(
                            main.ChatRequest(
                                conversation_id=conversation_id,
                                question="Outra pergunta falada.",
                                input_mode="voice",
                                audio_reservation_id=reservation.reservation_id,
                            )
                        )

        self.assertEqual(response.audio_remaining, main.AUDIO_LIMIT - 1)
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
