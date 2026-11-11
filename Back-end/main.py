from __future__ import annotations

import os
import re
import sqlite3
import sys
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Dados.rag.dataset import CSV_PATH, program_as_api_record, read_programs
from Dados.rag.rag import (
    KnowledgeBase,
    ModelUnavailableError,
    OUT_OF_SCOPE_RESPONSE,
    generate_answer,
)


AUDIO_LIMIT_DB = Path(
    os.environ.get("AUDIO_LIMIT_DB", PROJECT_ROOT / "Back-end" / "data" / "audio_limits.sqlite3")
)
AUDIO_LIMIT = 10
AUDIO_RESET_PERIOD = timedelta(hours=24)

STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "eu", "me", "meu", "minha", "o", "os", "para", "por", "qual",
    "quais", "que", "se", "tem", "tenho", "um", "uma", "quem", "pode",
    "criterios", "receber", "beneficio",
}


class Benefit(BaseModel):
    id: str
    agency_id: str
    name: str
    current_name: str
    summary: str
    category: str
    benefit_type: str
    audience: str
    criteria: list[str]
    criteria_status: str
    source_title: str
    source_page: str
    source_url: str
    legislation_base: str
    regulation: str
    recent_update: str
    legislation_reference_type: str
    validation_notes: str
    legislation_notes: str
    legislation_url: str
    research_date: str
    source_date: str
    scope: str


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AssistantResponse(BaseModel):
    answer: str
    benefits: list[Benefit]
    notice: str


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    input_mode: Literal["text", "voice"] = "text"
    history: list[ConversationMessage] = Field(default_factory=list, max_length=12)
    audio_reservation_id: UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, str]]
    notice: str
    audio_remaining: int
    audio_resets_at: str


class AudioReservationRequest(BaseModel):
    conversation_id: UUID


class AudioQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    resets_at: str | None
    reservation_id: UUID | None = None


def open_audio_limit_db() -> sqlite3.Connection:
    AUDIO_LIMIT_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUDIO_LIMIT_DB, timeout=10)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_audio_limits (
            conversation_id TEXT PRIMARY KEY,
            window_started_at TEXT NOT NULL,
            used INTEGER NOT NULL CHECK (used >= 0)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_reservations (
            reservation_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            window_started_at TEXT NOT NULL,
            consumed INTEGER NOT NULL DEFAULT 0 CHECK (consumed IN (0, 1))
        )
        """
    )
    return connection


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase()


def audio_quota(conversation_id: UUID) -> AudioQuotaResponse:
    now = datetime.now(timezone.utc)
    with closing(open_audio_limit_db()) as connection:
        row = connection.execute(
            """
            SELECT window_started_at, used
            FROM conversation_audio_limits
            WHERE conversation_id = ?
            """,
            (str(conversation_id),),
        ).fetchone()

    if row is None:
        return AudioQuotaResponse(limit=AUDIO_LIMIT, used=0, remaining=AUDIO_LIMIT, resets_at=None)

    window_started_at = datetime.fromisoformat(row[0])
    if now >= window_started_at + AUDIO_RESET_PERIOD:
        return AudioQuotaResponse(limit=AUDIO_LIMIT, used=0, remaining=AUDIO_LIMIT, resets_at=None)
    used = row[1]
    return AudioQuotaResponse(
        limit=AUDIO_LIMIT,
        used=used,
        remaining=AUDIO_LIMIT - used,
        resets_at=(window_started_at + AUDIO_RESET_PERIOD).isoformat(),
    )


def reserve_audio_turn(conversation_id: UUID) -> AudioQuotaResponse:
    now = datetime.now(timezone.utc)
    reservation_id = uuid4()
    with closing(open_audio_limit_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT window_started_at, used
                FROM conversation_audio_limits
                WHERE conversation_id = ?
                """,
                (str(conversation_id),),
            ).fetchone()

            if row is None or now >= datetime.fromisoformat(row[0]) + AUDIO_RESET_PERIOD:
                window_started_at = now
                used = 0
            else:
                window_started_at = datetime.fromisoformat(row[0])
                used = row[1]

            if used >= AUDIO_LIMIT:
                resets_at = window_started_at + AUDIO_RESET_PERIOD
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": "O limite de áudio desta conversa foi atingido.",
                        "remaining": 0,
                        "resets_at": resets_at.isoformat(),
                    },
                    headers={"Retry-After": str(max(1, int((resets_at - now).total_seconds())))},
                )

            expiration_before = (now - AUDIO_RESET_PERIOD).isoformat()
            connection.execute(
                "DELETE FROM audio_reservations WHERE window_started_at < ?",
                (expiration_before,),
            )
            connection.execute(
                "DELETE FROM conversation_audio_limits WHERE window_started_at < ?",
                (expiration_before,),
            )
            used += 1
            connection.execute(
                """
                INSERT INTO conversation_audio_limits (conversation_id, window_started_at, used)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    window_started_at = excluded.window_started_at,
                    used = excluded.used
                """,
                (str(conversation_id), window_started_at.isoformat(), used),
            )
            connection.execute(
                """
                INSERT INTO audio_reservations (
                    reservation_id, conversation_id, window_started_at, consumed
                ) VALUES (?, ?, ?, 0)
                """,
                (str(reservation_id), str(conversation_id), window_started_at.isoformat()),
            )
            resets_at = window_started_at + AUDIO_RESET_PERIOD

    return AudioQuotaResponse(
        limit=AUDIO_LIMIT,
        used=used,
        remaining=AUDIO_LIMIT - used,
        resets_at=resets_at.isoformat(),
        reservation_id=reservation_id,
    )


def consume_audio_reservation(conversation_id: UUID, reservation_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    with closing(open_audio_limit_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT window_started_at, consumed
                FROM audio_reservations
                WHERE reservation_id = ? AND conversation_id = ?
                """,
                (str(reservation_id), str(conversation_id)),
            ).fetchone()
            if (
                row is None
                or row[1] != 0
                or now >= datetime.fromisoformat(row[0]) + AUDIO_RESET_PERIOD
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A tentativa de áudio não é válida ou já foi utilizada.",
                )
            connection.execute(
                "UPDATE audio_reservations SET consumed = 1 WHERE reservation_id = ?",
                (str(reservation_id),),
            )


app = FastAPI(
    title="Assistente Institucional de Benefícios",
    description="Consulta informações institucionais revisadas sobre benefícios.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def load_programs(path: Path | None = None) -> list[Benefit]:
    try:
        rows = read_programs(path or CSV_PATH)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Não foi possível carregar a base local de programas sociais: {exc}",
        ) from exc

    try:
        return [Benefit.model_validate(program_as_api_record(row)) for row in rows]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Há um programa com estrutura inválida na base CSV.",
        ) from exc


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def search_terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", normalize(text))
        if len(term) > 2 and term not in STOP_WORDS
    }


def matching_benefits(question: str, benefits: list[Benefit]) -> list[Benefit]:
    terms = search_terms(question)
    if not terms:
        return []

    scored: list[tuple[int, Benefit]] = []
    for benefit in benefits:
        searchable_text = " ".join(
            [
                benefit.name,
                benefit.current_name,
                benefit.summary,
                benefit.category,
                benefit.benefit_type,
                benefit.audience,
                *benefit.criteria,
                benefit.legislation_base,
                benefit.regulation,
                benefit.recent_update,
                benefit.legislation_notes,
                benefit.validation_notes,
            ]
        )
        document_terms = search_terms(searchable_text)
        score = len(terms & document_terms)
        if score:
            scored.append((score, benefit))
    scored.sort(key=lambda result: result[0], reverse=True)
    return [benefit for _, benefit in scored[:3]]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/agencies")
def list_agencies() -> list[dict[str, str]]:
    agencies = sorted({benefit.agency_id for benefit in load_programs()})
    return [{"id": agency, "name": agency, "scope": "Federal"} for agency in agencies]


@app.get("/api/benefits", response_model=list[Benefit])
def list_benefits(
    agency_id: str | None = Query(default=None, min_length=2, max_length=100),
) -> list[Benefit]:
    benefits = load_programs()
    if agency_id is None:
        return benefits
    return [benefit for benefit in benefits if benefit.agency_id.casefold() == agency_id.casefold()]


@app.post("/api/assistant", response_model=AssistantResponse)
def ask_assistant(request: AssistantRequest) -> AssistantResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Escreva uma pergunta para continuar.")

    matches = matching_benefits(question, load_programs())
    if not matches:
        return AssistantResponse(
            answer=(
                "Ainda não encontrei um programa correspondente na base fornecida que responda a essa "
                "pergunta. Isso não significa que você não tenha direito a um benefício. "
                "Tente novamente com o nome do programa ou consulte o órgão responsável."
            ),
            benefits=[],
            notice="Não use esta resposta como decisão de elegibilidade.",
        )

    names = ", ".join(benefit.name for benefit in matches)
    return AssistantResponse(
        answer=f"Encontrei informações que podem ser relevantes: {names}.",
        benefits=matches,
        notice=(
            "A correspondência é apenas informativa e não confirma elegibilidade. "
            "Consulte as fontes oficiais indicadas em cada resultado."
        ),
    )


@app.get("/api/audio/quota", response_model=AudioQuotaResponse)
def get_audio_quota(
    conversation_id: UUID = Query(...),
) -> AudioQuotaResponse:
    return audio_quota(conversation_id)


@app.post("/api/audio/reserve", response_model=AudioQuotaResponse)
def reserve_audio(request: AudioReservationRequest) -> AudioQuotaResponse:
    return reserve_audio_turn(request.conversation_id)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Diga ou escreva sua pergunta para continuar.")

    if request.input_mode == "voice" and request.audio_reservation_id is None:
        raise HTTPException(
            status_code=409,
            detail="Reserve uma tentativa de áudio antes de enviar a pergunta falada.",
        )
    if request.input_mode == "voice":
        consume_audio_reservation(request.conversation_id, request.audio_reservation_id)

    quota = audio_quota(request.conversation_id)

    try:
        context = get_knowledge_base().search(question)
        answer = generate_answer(
            question,
            context,
            [message.model_dump() for message in request.history[-8:]],
        )
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    cited_context = [] if answer == OUT_OF_SCOPE_RESPONSE else context
    citations = [
        {
            "agency_id": item["agency_id"],
            "title": item["title"],
            "url": item["url"],
            "legislation_url": item["legislation_url"],
            "source_page": item["source_page"],
            "source_date": item["source_date"],
            "researched_at": item["researched_at"],
            "excerpt": item["text"],
        }
        for item in cited_context
    ]
    notice = (
        "Resposta informativa baseada nas fontes citadas. O órgão responsável decide "
        "sobre elegibilidade e atendimento."
        if citations
        else "Não foram usadas fontes recuperadas da base para esta resposta."
    )
    return ChatResponse(
        answer=answer,
        citations=citations,
        notice=notice,
        audio_remaining=quota.remaining,
        audio_resets_at=quota.resets_at or "",
    )
