from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Dados.rag.dataset import (
    CSV_PATH,
    build_official_source_chunks,
    build_program_chunks,
    program_as_api_record,
    read_programs,
)
from Dados.rag.ingestao import write_program_documents
from Dados.rag.fontes import source_filename
from Dados.rag.rag import is_official_url


class ProgramDatasetTests(unittest.TestCase):
    def test_csv_encoding_and_program_rows_are_preserved(self) -> None:
        rows = read_programs()

        self.assertEqual(len(rows), 42)
        self.assertEqual(
            rows[0]["programa"],
            "Ação de Distribuição de Alimentos (ADA)",
        )
        self.assertEqual(len({row["programa"] for row in rows}), 42)
        self.assertEqual(len({row["url_fonte"] for row in rows}), 1)
        self.assertEqual(
            len({row["url_fonte_legislacao"] for row in rows if row["url_fonte_legislacao"]}),
            30,
        )
        self.assertEqual(
            sum(row["status_criterio"] == "Informação parcial no documento" for row in rows),
            30,
        )
        self.assertEqual(
            sum(row["status_criterio"] == "Critérios não especificados no documento" for row in rows),
            12,
        )

    def test_latin1_export_is_supported_as_a_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "programas-latin1.csv"
            csv_text = CSV_PATH.read_text(encoding="utf-8-sig")
            csv_path.write_bytes(
                b"\xef\xbb\xbf" + csv_text.encode("latin-1", errors="replace")
            )

            rows = read_programs(csv_path)

        self.assertEqual(rows[0]["programa"], "Ação de Distribuição de Alimentos (ADA)")

    def test_csv_builds_four_contextual_chunks_per_program(self) -> None:
        chunks = build_program_chunks(read_programs())

        self.assertEqual(len(chunks), 168)
        self.assertEqual(len({chunk.metadata["program_id"] for chunk in chunks}), 42)
        self.assertIn("Ação de Distribuição de Alimentos", chunks[0].text)
        self.assertEqual(chunks[0].metadata["dataset_version"], "programas-sociais-legislacao-v2")
        self.assertEqual(chunks[0].metadata["region"], "DF")

    def test_official_legislation_chunks_require_twenty_complete_sources(self) -> None:
        rows = read_programs()
        unique_rows = {
            row["url_fonte_legislacao"]: row
            for row in rows
            if row["url_fonte_legislacao"]
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            for url, row in list(unique_rows.items())[:20]:
                metadata = {
                    "url": url,
                    "title": row["legislacao_base"],
                    "retrieved_at": "2026-11-05T00:00:00+00:00",
                }
                source_file = source_dir / source_filename(url)
                source_file.write_text(
                    "---SOURCE-METADATA---\n"
                    + json.dumps(metadata, ensure_ascii=False)
                    + "\n---SOURCE-TEXT---\n"
                    + ("Art. 1º Este texto legal descreve direitos e procedimentos. " * 25),
                    encoding="utf-8",
                )

            chunks = build_official_source_chunks(rows, source_dir)

        self.assertGreaterEqual(len({chunk.metadata["url"] for chunk in chunks}), 20)
        self.assertTrue(all(chunk.metadata["source_kind"] == "legislation" for chunk in chunks))
        self.assertTrue(any("Art. 1º Este texto legal" in chunk.text for chunk in chunks))

    def test_official_legislation_chunks_reject_incomplete_corpus(self) -> None:
        rows = read_programs()

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "pelo menos 20"):
                build_official_source_chunks(rows, Path(temporary_directory))

    def test_missing_criteria_are_not_invented_for_api_or_index(self) -> None:
        row = next(row for row in read_programs() if not row["criterios_elegibilidade_resumidos"])
        api_record = program_as_api_record(row)
        indexed_criteria = next(
            chunk
            for chunk in build_program_chunks([row])
            if chunk.metadata["section"] == "Público e critérios"
        )

        self.assertEqual(api_record["criteria"], [])
        self.assertIn("Não especificados no documento de origem.", indexed_criteria.text)
        self.assertIn(row["status_criterio"], indexed_criteria.text)

    def test_missing_audience_is_explicit_in_the_indexed_document(self) -> None:
        row = next(row for row in read_programs() if not row["descricao_publico_alvo"])
        api_record = program_as_api_record(row)
        document = build_program_chunks([row])

        self.assertEqual(api_record["audience"], "")
        self.assertIn(
            "Público-alvo: Não especificado no documento de origem.",
            document[0].text
            + next(
                chunk.text
                for chunk in document
                if chunk.metadata["section"] == "Público e critérios"
            ),
        )

    def test_source_links_must_be_https_and_official(self) -> None:
        self.assertTrue(is_official_url("https://www.gov.br/servicos"))
        self.assertTrue(is_official_url("https://www2.camara.leg.br/legislacao"))
        self.assertFalse(is_official_url("http://www.gov.br/servicos"))
        self.assertFalse(is_official_url("https://gov.br.example.com/servicos"))

    def test_invalid_primary_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "programas.csv"
            csv_path.write_bytes(
                CSV_PATH.read_bytes().replace(
                    b"https://mds.gov.br/",
                    b"http://mds.gov.br/",
                    1,
                )
            )

            with self.assertRaisesRegex(ValueError, "domínio oficial"):
                read_programs(csv_path)

    def test_document_generation_replaces_stale_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory)
            (output_path / "antigo.md").write_text("Conteúdo anterior.", encoding="utf-8")
            rows = read_programs()[:1]

            with patch("Dados.rag.ingestao.BASE_PATH", output_path):
                generated = write_program_documents(rows)

            files = list(output_path.glob("*.md"))
            self.assertEqual(generated, 1)
            self.assertEqual(
                [path.name for path in files],
                ["acao-de-distribuicao-de-alimentos-ada.md"],
            )
            self.assertIn("Legislação base:", files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
