from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

import chromadb
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from RAG import rag
from RAG.rag import DATASET_VERSION, KnowledgeBase, SourceChunk


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

    def test_query_expansion_does_not_confuse_housework_with_housing(self) -> None:
        expanded = rag.expand_question("Sou dona de casa e quero pagar o INSS mais barato")

        self.assertIn("facultativo baixa renda", expanded)
        self.assertNotIn("moradia habitacao", expanded)

    def test_query_expansion_links_single_mothers_to_family_income_support(self) -> None:
        expanded = rag.expand_question("Quais benefícios para mãe solteira de baixa renda?")

        self.assertIn("Bolsa Familia", expanded)
        self.assertIn("transferencia de renda", expanded)

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

        with patch("RAG.rag.embed_texts", return_value=[[1.0, 0.0]]):
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

        with patch("RAG.rag.embed_texts", return_value=[[1.0, 0.0]]):
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

    def test_search_abstains_when_similarity_is_below_threshold(self) -> None:
        knowledge_base = KnowledgeBase(client=self.client)
        knowledge_base.replace(
            [source_chunk("unrelated", "other", "Outro programa", "Outro assunto.")],
            [[0.0, 1.0]],
        )

        with patch("RAG.rag.embed_texts", return_value=[[1.0, 0.0]]):
            results = knowledge_base.search("Como pedir o benefício?")

        self.assertEqual(results, [])

    def test_answer_uses_curated_fields_without_a_generation_model(self) -> None:
        source = {
            "agency_id": "MDS",
            "program_name": "Bolsa Família",
            "current_name": "",
            "summary": "Transferência de renda para famílias.",
            "benefit_type": "Benefício mensal",
            "audience": "Famílias em situação de pobreza.",
            "criteria": "A base não detalha os critérios.",
            "criteria_status": "Informação parcial no documento",
            "legislation_base": "Lei nº 14.601/2023",
        }
        answer = rag.compose_answer([source])

        self.assertIn("Bolsa Família [1]", answer)
        self.assertIn("Critérios descritos na base:", answer)
        self.assertIn("informação sobre os critérios é parcial", answer)
        self.assertIn("Lei nº 14.601/2023", answer)
        self.assertIn("Órgão responsável informado na base: MDS", answer)

    def test_answer_abstains_without_retrieved_evidence(self) -> None:
        self.assertEqual(rag.compose_answer([]), rag.NO_CONTEXT_RESPONSE)

    def test_answer_lists_other_retrieved_programs_by_name_only(self) -> None:
        answer = rag.compose_answer(
            [
                {"program_name": "BPC"},
                {"program_name": "Bolsa Família"},
            ]
        )

        self.assertIn("BPC [1]", answer)
        self.assertIn("Outros resultados relacionados: Bolsa Família [2].", answer)


if __name__ == "__main__":
    unittest.main()
