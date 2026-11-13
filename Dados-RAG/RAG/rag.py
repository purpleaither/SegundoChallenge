from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


RAG_ROOT = Path(__file__).resolve().parent
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA")
DEFAULT_VECTOR_DB_PATH = (
    Path(LOCAL_APP_DATA) / "AssistenteVirtualDF" / "vetor-v3"
    if os.name == "nt" and LOCAL_APP_DATA
    else RAG_ROOT.parent / "vetor-v3"
)
VECTOR_DB_PATH = Path(os.environ.get("VECTOR_DB_PATH") or DEFAULT_VECTOR_DB_PATH)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "bge-m3")
RAG_MIN_SIMILARITY = float(os.environ.get("RAG_MIN_SIMILARITY", "0.532"))
OLLAMA_EVALUATION_MODEL = os.environ.get("OLLAMA_EVALUATION_MODEL", "qwen2.5:3b")
COLLECTION_NAME = "fontes_oficiais_df"
DATASET_VERSION = "programas-sociais-legislacao-v3"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 180
NO_CONTEXT_RESPONSE = (
    "Não encontrei informação suficientemente relacionada na base para responder. "
    "Isso não significa que você não tenha direito a um benefício. "
    "Tente reformular a pergunta ou consulte um órgão oficial."
)

QUERY_EXPANSIONS = {
    "absorv": "dignidade menstrual absorventes",
    "agua": "cisternas tarifa social agua saneamento",
    "aluguel": "moradia habitacao",
    "baixa renda": "CadÚnico pobreza transferência de renda Bolsa Família",
    "botij": "auxilio gas GLP",
    "bebe": "primeira infancia criancas",
    "cesta": "alimentos distribuicao seguranca alimentar",
    "comida": "alimentos seguranca alimentar cesta",
    "deficien": "pessoa com deficiencia BPC auxilio inclusao",
    "dona de casa": "INSS facultativo baixa renda contribuicao previdenciaria trabalho domestico",
    "desempreg": "baixa renda transferencia de renda",
    "ensino medio": "Pe-de-Meia ensino medio",
    "faculdade": "ensino superior FIES PNAES Sisu",
    "fome": "inseguranca alimentar distribuicao de alimentos",
    "gas": "auxilio gas GLP",
    "gestant": "primeira infancia acompanhamento",
    "idos": "pessoa idosa BPC",
    "inss": "facultativo baixa renda contribuicao previdenciaria trabalho domestico",
    "luz": "energia eletrica tarifa social",
    "mae solteira": "Bolsa Familia transferencia de renda familia pobreza CadUnico",
    "onib": "passe livre transporte interestadual",
    "remedio": "medicamentos farmacia popular",
    "roca": "rural agricultura familiar",
    "casa": "moradia habitacao",
    "seca": "cisternas agua zona rural",
}


class ModelUnavailableError(RuntimeError):
    pass


if not 0 <= RAG_MIN_SIMILARITY <= 1:
    raise ValueError("RAG_MIN_SIMILARITY precisa estar entre 0 e 1.")


@dataclass(frozen=True)
class SourceChunk:
    id: str
    text: str
    metadata: dict[str, str]


def is_official_url(url: str) -> bool:
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname or ""
    return parsed_url.scheme == "https" and any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("gov.br", "leg.br")
    )


def expand_question(question: str) -> str:
    decomposed = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    expansions = [
        expansion
        for term, expansion in QUERY_EXPANSIONS.items()
        if re.search(rf"\b{re.escape(term)}", normalized)
        and not (
            term == "casa"
            and re.search(r"\bdona de casa\b", normalized)
        )
    ]
    return " ".join(dict.fromkeys((question, *expansions)))


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("O tamanho do trecho e a sobreposição são inválidos.")

    normalized_text = "\n".join(line.strip() for line in text.splitlines()).strip()
    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        if end < len(normalized_text):
            boundary = normalized_text.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        chunk = normalized_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized_text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def request_ollama(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{OLLAMA_URL}{endpoint}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError(
            "Não foi possível acessar o Ollama para gerar embeddings. Inicie o serviço "
            "local e confira o modelo de embeddings configurado."
        ) from exc
    if not isinstance(result, dict):
        raise ModelUnavailableError("O Ollama retornou embeddings em formato inválido.")
    return result


def embed_texts(texts: list[str]) -> list[list[float]]:
    result = request_ollama(
        "/api/embed",
        {"model": OLLAMA_EMBEDDING_MODEL, "input": texts},
    )
    embeddings = result.get("embeddings")
    if (
        not isinstance(embeddings, list)
        or len(embeddings) != len(texts)
        or any(
            not isinstance(vector, list)
            or not vector
            or any(not isinstance(value, (int, float)) for value in vector)
            for vector in embeddings
        )
    ):
        raise ModelUnavailableError("O modelo de embeddings retornou vetores inválidos.")
    return embeddings


def compose_answer(context: list[dict[str, Any]]) -> str:
    if not context:
        return NO_CONTEXT_RESPONSE

    source = context[0]
    program_name = source.get("program_name") or "Programa encontrado"
    current_name = source.get("current_name", "").strip()
    agency = source.get("agency_id", "").strip()
    summary = source.get("summary", "").strip()
    benefit_type = source.get("benefit_type", "").strip()
    audience = source.get("audience", "").strip()
    criteria = source.get("criteria", "").strip()
    criteria_status = source.get("criteria_status", "").strip()
    legislation = source.get("legislation_base", "").strip()
    regulation = source.get("regulation", "").strip()
    citation = "[1]"

    answer = [f"{program_name} {citation}."]
    if current_name and current_name.casefold() != program_name.casefold():
        answer.append(f"Nome atual indicado na base: {current_name}.")
    if summary:
        answer.append(summary)
    if benefit_type:
        answer.append(f"Tipo de benefício informado: {benefit_type}.")
    if audience:
        answer.append(f"Público informado: {audience}")
    else:
        answer.append("A base não especifica o público-alvo.")
    if criteria:
        answer.append(f"Critérios descritos na base: {criteria}")
    else:
        answer.append("A base não especifica os critérios de elegibilidade.")
    if criteria_status and "parcial" in criteria_status.casefold():
        answer.append("A informação sobre os critérios é parcial; confirme os detalhes na fonte oficial.")
    if legislation:
        answer.append(f"Legislação base informada: {legislation}.")
    if regulation:
        answer.append(f"Regulamentação informada: {regulation}.")
    if source.get("recent_update", "").strip():
        answer.append(f"Atualização normativa registrada: {source['recent_update'].strip()}.")
    if agency:
        answer.append(f"Órgão responsável informado na base: {agency}.")
    answer.append(
        "Esta orientação é informativa e não confirma elegibilidade; consulte a fonte oficial."
    )
    if len(context) > 1:
        related = ", ".join(
            f"{item.get('program_name') or 'Programa'} [{index}]"
            for index, item in enumerate(context[1:], start=2)
        )
        answer.append(f"Outros resultados relacionados: {related}.")
    return " ".join(answer)


class KnowledgeBase:
    def __init__(self, path: Path = VECTOR_DB_PATH, client: Any | None = None) -> None:
        if client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise ModelUnavailableError(
                    "O banco vetorial não está instalado. Instale as dependências do back-end."
                ) from exc
            client = chromadb.PersistentClient(path=str(path))
        self._client = client
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def close(self) -> None:
        self._client.close()

    def replace(self, chunks: list[SourceChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Cada trecho precisa ter um vetor correspondente.")
        existing_ids = self._collection.get(include=["metadatas"])["ids"]
        if existing_ids:
            self._collection.delete(ids=existing_ids)
        if not chunks:
            return
        self._collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=embeddings,
        )

    def search(self, question: str, limit: int = 4) -> list[dict[str, Any]]:
        collection_count = self._collection.count()
        if not collection_count or limit <= 0:
            return []
        query_embeddings = embed_texts([expand_question(question)])
        result = self._collection.query(
            query_embeddings=query_embeddings,
            n_results=min(collection_count, limit * 8),
            where={
                "$and": [
                    {"dataset_version": {"$eq": DATASET_VERSION}},
                    {"region": {"$eq": "DF"}},
                ]
            },
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        matches_by_program: dict[str, dict[str, Any]] = {}
        for text, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
            if not isinstance(text, str) or not isinstance(metadata, dict):
                continue
            similarity = 1 - float(distance)
            if similarity < RAG_MIN_SIMILARITY:
                continue
            program_id = metadata.get("program_id") or metadata.get("title", text)
            matches_by_program.setdefault(
                program_id,
                {
                    "text": text,
                    "agency_id": metadata.get("agency_id", ""),
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "legislation_url": metadata.get("legislation_url", ""),
                    "source_page": metadata.get("source_page", ""),
                    "source_date": metadata.get("source_date", ""),
                    "researched_at": metadata.get("researched_at", ""),
                    "criteria_status": metadata.get("criteria_status", ""),
                    "program_id": metadata.get("program_id", ""),
                    "program_name": metadata.get("program_name", ""),
                    "current_name": metadata.get("current_name", ""),
                    "summary": metadata.get("summary", ""),
                    "benefit_type": metadata.get("benefit_type", ""),
                    "audience": metadata.get("audience", ""),
                    "criteria": metadata.get("criteria", ""),
                    "legislation_base": metadata.get("legislation_base", ""),
                    "regulation": metadata.get("regulation", ""),
                    "recent_update": metadata.get("recent_update", ""),
                    "legislation_notes": metadata.get("legislation_notes", ""),
                    "distance": float(distance),
                    "similarity": similarity,
                },
            )
        return list(matches_by_program.values())[:limit]
