"""Local pt-BR neural TTS. User text and generated WAV stay in memory."""
from __future__ import annotations

import io
import os
import threading
import wave
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

MODEL_NAME = "pt_BR-faber-medium"
DEFAULT_MODEL = Path(__file__).parent / "voices" / f"{MODEL_NAME}.onnx"
router = APIRouter(prefix="/api/tts", tags=["TTS"])


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Texto vazio.")
        return value


class SpeechUnavailable(Exception):
    pass


class SpeechBusy(Exception):
    pass


class LocalSpeech:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.voice = None
        self.lock = threading.Lock()

    def load(self):
        if self.voice is not None:
            return self.voice
        if not self.model_path.is_file() or not Path(f"{self.model_path}.json").is_file():
            raise SpeechUnavailable("Voice model not installed")
        try:
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from piper import PiperVoice
            self.voice = PiperVoice.load(str(self.model_path), use_cuda=False)
        except Exception as error:
            raise SpeechUnavailable("Unable to load TTS engine") from error
        return self.voice

    def synthesize(self, text: str) -> bytes:
        if not self.lock.acquire(blocking=False):
            raise SpeechBusy()
        try:
            voice = self.load()
            output = io.BytesIO()
            with wave.open(output, "wb") as wav:
                voice.synthesize_wav(text, wav)
            audio = output.getvalue()
            if len(audio) <= 44 or not audio.startswith(b"RIFF"):
                raise SpeechUnavailable("No audio generated")
            return audio
        except SpeechUnavailable:
            raise
        except Exception as error:
            raise SpeechUnavailable("Unable to synthesize audio") from error
        finally:
            self.lock.release()


@lru_cache(maxsize=1)
def get_speech() -> LocalSpeech:
    return LocalSpeech(Path(os.environ.get("TTS_MODEL_PATH", str(DEFAULT_MODEL))))


@router.get("/health")
def health():
    service = get_speech()
    if service.voice is None:
        raise HTTPException(503, "A voz ainda não está pronta.")
    return {"status": "ok", "engine": "piper", "voice": MODEL_NAME, "language": "pt-BR"}


@router.post("")
async def synthesize(body: SpeechRequest):
    try:
        audio = await run_in_threadpool(get_speech().synthesize, body.text)
    except SpeechBusy:
        raise HTTPException(429, "A voz está ocupada. Tente novamente em instantes.", headers={"Retry-After": "1"})
    except SpeechUnavailable:
        raise HTTPException(503, "Não foi possível gerar o áudio. Tente novamente em instantes.")
    return Response(audio, media_type="audio/wav", headers={
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
    })


@asynccontextmanager
async def lifespan(_app: FastAPI):
    service = get_speech()
    await run_in_threadpool(service.load)
    # Warm up the model before accepting requests. No user content is involved.
    await run_in_threadpool(service.synthesize, "Olá.")
    yield
    service.voice = None
    get_speech.cache_clear()


app = FastAPI(title="GuIA Social — TTS", lifespan=lifespan)
app.include_router(router)
