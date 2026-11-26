"""Local Portuguese transcription. Request audio remains in memory."""
import io
import os
import threading
from contextlib import asynccontextmanager

import av
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

MAX_BYTES = 8 * 1024 * 1024
MAX_SECONDS = 60
MODEL_NAME = os.environ.get('STT_MODEL', 'small')
PREVIEW_MODEL_NAME = os.environ.get('STT_PREVIEW_MODEL', 'small')
model = None
preview_model = None
lock = threading.Lock()


def decode_audio(data):
    chunks, count = [], 0
    try:
        with av.open(io.BytesIO(data)) as container:
            if not container.streams.audio:
                raise ValueError('No audio')
            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
            for frame in container.decode(audio=0):
                for output in resampler.resample(frame):
                    count += output.samples
                    if count > MAX_SECONDS * 16000:
                        raise HTTPException(413, 'Grave no máximo 60 segundos.')
                    chunks.append(output.to_ndarray().flatten())
            for output in resampler.resample(None):
                count += output.samples
                if count > MAX_SECONDS * 16000:
                    raise HTTPException(413, 'Grave no máximo 60 segundos.')
                chunks.append(output.to_ndarray().flatten())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'Áudio inválido. Grave novamente.')
    if not count:
        raise HTTPException(422, 'Não há áudio na gravação.')
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcribe(data, preview=False):
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'Transcrição ocupada. Tente novamente.', headers={'Retry-After':'1'})
    try:
        selected = preview_model if preview else model
        if selected is None:
            raise HTTPException(503, 'Transcrição indisponível. Tente novamente.')
        audio = decode_audio(data)
        segments, _ = selected.transcribe(audio, language='pt', beam_size=3 if preview else 5,
            vad_filter=True, vad_parameters={'min_silence_duration_ms': 500, 'speech_pad_ms': 300},
            condition_on_previous_text=True, temperature=0.0)
        text = ' '.join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()
        return {'text': text, 'language': 'pt-BR'}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Não foi possível transcrever. Tente novamente.')
    finally:
        lock.release()


@asynccontextmanager
async def lifespan(app):
    global model, preview_model
    from faster_whisper import WhisperModel
    model = await run_in_threadpool(lambda: WhisperModel(MODEL_NAME, device='cpu', compute_type='int8', cpu_threads=4,
        download_root=os.environ.get('STT_MODEL_DIR'), local_files_only=True))
    preview_model = model if PREVIEW_MODEL_NAME == MODEL_NAME else await run_in_threadpool(lambda: WhisperModel(
        PREVIEW_MODEL_NAME, device='cpu', compute_type='int8', cpu_threads=4,
        download_root=os.environ.get('STT_MODEL_DIR'), local_files_only=True))
    yield
    model = None
    preview_model = None


app = FastAPI(title='GuIA Social — STT', lifespan=lifespan)


@app.get('/api/stt/health')
def health():
    if model is None or preview_model is None:
        raise HTTPException(503, 'Modelo ainda não está pronto.')
    return {'status':'ok', 'engine':'faster-whisper', 'model':MODEL_NAME, 'preview_model':PREVIEW_MODEL_NAME, 'language':'pt-BR'}


@app.post('/api/stt')
async def speech(request: Request, preview: bool = False):
    if request.headers.get('content-type', '').split(';')[0] not in {
        'audio/webm', 'audio/mp4', 'audio/ogg', 'audio/wav', 'audio/x-wav'}:
        raise HTTPException(415, 'Formato de áudio não suportado.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, 'Áudio muito grande. Grave no máximo 60 segundos.')
        data.extend(chunk)
    if not data:
        raise HTTPException(422, 'Gravação vazia.')
    result = await run_in_threadpool(transcribe, bytes(data), preview)
    from fastapi.responses import JSONResponse
    return JSONResponse(result, headers={'Cache-Control':'no-store, private'})
