from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sistema_multiagente import rag


class RawRetrievalTests(unittest.TestCase):
    def test_empty_knowledge_base_search_returns_no_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            vector_db_path = Path(temporary_directory)
            with (
                patch.object(rag, "KnowledgeBase") as knowledge_base,
                patch.object(rag, "VECTOR_DB_PATH", vector_db_path),
                patch.object(rag, "_mapa_programas", return_value={}),
            ):
                knowledge_base.return_value.search.return_value = []
                results = rag._buscar_trechos_brutos("Como está o campeonato?")

            self.assertEqual(results, [])
            knowledge_base.return_value.close.assert_called_once_with()

    def test_model_unavailability_is_reported_instead_of_falling_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            vector_db_path = Path(temporary_directory)
            with (
                patch.object(rag, "KnowledgeBase") as knowledge_base,
                patch.object(rag, "VECTOR_DB_PATH", vector_db_path),
                patch.object(rag, "_mapa_programas", return_value={}),
            ):
                knowledge_base.return_value.search.side_effect = rag.ModelUnavailableError(
                    "Ollama indisponível."
                )

                with self.assertRaisesRegex(rag.ModelUnavailableError, "Ollama indisponível"):
                    rag._buscar_trechos_brutos("Como está o campeonato?")

            knowledge_base.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
