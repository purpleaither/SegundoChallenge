from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

import chromadb
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from Dados.rag import rag
from Dados.rag.rag import DATASET_VERSION, KnowledgeBase, SourceChunk


def source_chunk(
    chunk_id: str,
    program_id: str,
    program_name: str,
    text: str,
) -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        text=text,
        metadata={
            "dataset_version": DATASET_VERSION,
            "program_id": program_id,
            "program_name": program_name,
            "agency_id": "MDS",
            "title": "Fonte oficial",
            "url": "https://www.gov.br/exemplo.pdf",
            "legislation_url": "https://www.gov.br/lei",
            "source_page": "2",
            "source_date": "2025-04",
            "researched_at": "2026-11-04",
            "criteria_status": "Informação parcial",
            "region": "DF",
            "jurisdiction": "Federal",
            "section": "Sobre o programa",
        },
    )


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = chromadb.EphemeralClient(Settings(allow_reset=True))
        self.client.reset()

    def test_query_expansion_adds_portuguese_equivalents(self) -> None:
        expanded = rag.expand_question("Tem desconto no botijão?")

        self.assertIn("Tem desconto no botijão?", expanded)
        self.assertIn("auxilio gas GLP", expanded)

    def test_search_deduplicates_chunks_by_program(self) -> None:
        knowledge_base = KnowledgeBase(client=self.client)
        chunks = [
            source_chunk("bpc-1", "bpc", "BPC", "Critérios do BPC."),
            source_chunk("bpc-2", "bpc", "BPC", "Legislação do BPC."),
            source_chunk("bolsa-1", "bolsa", "Bolsa Família", "Critérios do Bolsa Família."),
            source_chunk("unrelated-1", "unrelated", "Programa distante", "Outro assunto."),
        ]
        knowledge_base.replace(
            chunks,
            [[1.0, 0.0], [0.99, 0.1], [0.9, 0.2], [-1.0, 0.0]],
        )

        with patch("Dados.rag.rag.embed_texts", return_value=[[1.0, 0.0]]):
            results = knowledge_base.search("Quem pode receber?", limit=2)

        self.assertEqual(
            [result["program_name"] for result in results],
            ["BPC", "Bolsa Família"],
        )
        self.assertTrue(all(result["url"].startswith("https://") for result in results))
        stored_ids = self.client.get_collection(rag.COLLECTION_NAME).get()["ids"]
        self.assertEqual(
            set(stored_ids),
            {"bpc-1", "bpc-2", "bolsa-1", "unrelated-1"},
        )
        self.assertNotIn("Programa distante", [result["program_name"] for result in results])

    def test_search_ignores_vectors_from_the_previous_corpus(self) -> None:
        collection = self.client.get_or_create_collection(
            rag.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(
            ids=["legacy-1"],
            documents=["Conteúdo da base anterior."],
            metadatas=[
                {
                    "dataset_version": "legacy",
                    "region": "DF",
                    "program_id": "legacy",
                    "program_name": "Programa antigo",
                }
            ],
            embeddings=[[1.0, 0.0]],
        )
        knowledge_base = KnowledgeBase(client=self.client)

        with patch("Dados.rag.rag.embed_texts", return_value=[[1.0, 0.0]]):
            results = knowledge_base.search("Conteúdo antigo.")

        self.assertEqual(results, [])

    def test_persistent_index_is_readable_after_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vector-db"
            writer = KnowledgeBase(path=path)
            writer.replace(
                [source_chunk("persisted", "program", "Programa", "Texto indexado.")],
                [[1.0, 0.0]],
            )
            writer.close()

            reader = KnowledgeBase(path=path)
            try:
                self.assertEqual(reader._collection.count(), 1)
            finally:
                reader.close()

    def test_answer_prompt_uses_planilha_chunks_and_cites_their_official_links(self) -> None:
        source = {
            "agency_id": "MDS",
            "program_name": "Auxílio Gás dos Brasileiros",
            "criteria_status": "Informação parcial no documento",
            "title": "Lista de Programas Federais",
            "url": "https://www.gov.br/programas.pdf",
            "legislation_url": "https://www.gov.br/lei",
            "source_page": "2",
            "researched_at": "2026-11-04",
            "text": "Critérios parcialmente especificados.",
        }
        with patch(
            "Dados.rag.rag.request_openai",
            side_effect=[
                '{"scope":"in_scope"}',
                "Consulte o órgão [1].",
            ],
        ) as request:
            answer = rag.generate_answer("Como solicitar?", [source], [])

        scope_prompt = request.call_args_list[0].args[0][0]["content"]
        self.assertIn("não use palavras isoladas", scope_prompt)
        self.assertEqual(request.call_args_list[0].kwargs["json_object"], True)
        system_message = request.call_args_list[1].args[0][0]["content"]
        self.assertIn("trechos recuperados da base de conhecimento", system_message)
        self.assertIn("Programa: Auxílio Gás dos Brasileiros", system_message)
        self.assertIn("órgão responsável informado: MDS", system_message)
        self.assertIn("não deduza um órgão pelo tema", system_message)
        self.assertIn(source["url"], system_message)
        self.assertIn(source["legislation_url"], system_message)
        self.assertIn("não complete as lacunas", system_message)
        self.assertEqual(request.call_args_list[1].kwargs["model"], None)
        self.assertEqual(answer, "Consulte o órgão [1].")

    def test_out_of_scope_question_is_abstained_before_answer_generation(self) -> None:
        with patch(
            "Dados.rag.rag.request_openai",
            return_value='{"scope":"out_of_scope"}',
        ) as request:
            answer = rag.generate_answer(
                "Como faço um bolo de cenoura para a assistência social?",
                [{"text": "Programa Bolsa Família"}],
                [],
            )

        self.assertEqual(answer, rag.OUT_OF_SCOPE_RESPONSE)
        self.assertEqual(request.call_count, 1)

    def test_scope_classifier_rejects_malformed_model_output(self) -> None:
        with patch(
            "Dados.rag.rag.request_openai",
            return_value="talvez",
        ):
            with self.assertRaises(rag.ModelUnavailableError):
                rag.question_is_in_scope("Qual a previsão do tempo?")

    def test_in_scope_question_without_context_returns_no_context_notice(self) -> None:
        with patch(
            "Dados.rag.rag.request_openai",
            return_value='{"scope":"in_scope"}',
        ) as request:
            answer = rag.generate_answer("Quais benefícios existem no DF?", [], [])

        self.assertEqual(answer, rag.NO_CONTEXT_RESPONSE)
        self.assertEqual(request.call_count, 1)

    def test_answer_falls_back_to_retrieved_text_when_model_omits_citations(self) -> None:
        source = {
            "agency_id": "MDS",
            "program_name": "Auxílio Gás dos Brasileiros",
            "title": "Lista de Programas Federais",
            "url": "https://www.gov.br/programas.pdf",
            "text": "Auxílio para compra de GLP.",
        }
        with patch(
            "Dados.rag.rag.request_openai",
            side_effect=[
                '{"scope":"in_scope"}',
                "Procure o Ministério da Saúde.",
            ],
        ):
            answer = rag.generate_answer("Como conseguir gás?", [source], [])

        self.assertIn("Auxílio para compra de GLP. [1]", answer)
        self.assertIn("órgão responsável informado é MDS", answer)
        self.assertNotIn("Ministério da Saúde", answer)

    def test_answer_falls_back_when_model_uses_an_invalid_citation(self) -> None:
        source = {
            "agency_id": "MDS",
            "program_name": "Auxílio Gás dos Brasileiros",
            "title": "Lista de Programas Federais",
            "url": "https://www.gov.br/programas.pdf",
            "text": "Auxílio para compra de GLP.",
        }
        with patch(
            "Dados.rag.rag.request_openai",
            side_effect=[
                '{"scope":"in_scope"}',
                "Consulte [2].",
            ],
        ):
            answer = rag.generate_answer("Como conseguir gás?", [source], [])

        self.assertIn("Auxílio para compra de GLP. [1]", answer)
        self.assertNotIn("Consulte [2]", answer)


if __name__ == "__main__":
    unittest.main()
