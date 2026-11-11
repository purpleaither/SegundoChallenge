from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from Dados.rag.fontes import extract_official_html, source_title_from_url


class OfficialSourceParsingTests(unittest.TestCase):
    def test_html_extraction_keeps_legislation_and_ignores_navigation(self) -> None:
        legal_text = "Art. 1º Este texto legal define o programa e seus critérios. " * 20
        html = (
            "<html><head><title>Metadados</title></head><body>"
            "<nav>Menu que não deve ser indexado</nav>"
            f"<main><h1>Lei nº 12.345</h1><p>{legal_text}</p></main>"
            "<script>instrução não deve ser indexada</script>"
            "</body></html>"
        ).encode("utf-8")

        extracted = extract_official_html(html)

        self.assertIn("Art. 1º", extracted)
        self.assertNotIn("Menu que não deve ser indexado", extracted)
        self.assertNotIn("Metadados", extracted)
        self.assertNotIn("instrução não deve ser indexada", extracted)

    def test_html_extraction_rejects_error_pages(self) -> None:
        html = (
            "<html><body><h1>504 Gateway Time-out</h1>"
            + "<p>Art. 1º indisponível</p>" * 50
            + "</body></html>"
        ).encode("utf-8")

        with self.assertRaisesRegex(ValueError, "mensagem de erro"):
            extract_official_html(html)

    def test_source_title_matches_the_linked_legislation(self) -> None:
        title = source_title_from_url(
            "https://www2.camara.leg.br/legin/fed/lei/2026/"
            "lei-15348-13-fevereiro-2026-798716-publicacaooriginal-178121-pl.html",
            "Lei nº 14.237/2021",
        )

        self.assertEqual(title, "Lei nº 15.348/2026")


if __name__ == "__main__":
    unittest.main()
