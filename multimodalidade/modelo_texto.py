"""Modelo multimodal textual: transforma uma pergunta em texto em resposta e citações.

Este módulo usa o mesmo RAG do projeto: expansão da pergunta, embedding bge-m3,
recuperação no ChromaDB e montagem determinística da resposta.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Dados-RAG"))

from RAG.rag import KnowledgeBase, compose_answer


@dataclass(frozen=True)
class RespostaTexto:
    modalidade: str
    pergunta: str
    resposta: str
    citacoes: list[dict[str, str]]


class ModeloTexto:
    """Entrada: texto; saída: resposta textual baseada em fontes oficiais."""

    def __init__(self) -> None:
        self._base = KnowledgeBase()

    def processar(self, pergunta: str) -> RespostaTexto:
        pergunta_limpa = pergunta.strip()
        if not pergunta_limpa:
            raise ValueError("A pergunta não pode estar vazia.")

        contexto = self._base.search(pergunta_limpa)
        citacoes = [
            {
                "agency_id": item.get("agency_id", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "excerpt": item.get("text", "")[:500],
            }
            for item in contexto
        ]
        return RespostaTexto(
            modalidade="texto",
            pergunta=pergunta_limpa,
            resposta=compose_answer(contexto),
            citacoes=citacoes,
        )

    def como_dict(self, pergunta: str) -> dict:
        return asdict(self.processar(pergunta))
