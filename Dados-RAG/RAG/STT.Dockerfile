FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 STT_MODEL_DIR=/app/models HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app
COPY requirements-stt.txt .
RUN pip install -r requirements-stt.txt
RUN python -c "from faster_whisper import WhisperModel; [WhisperModel(name, device='cpu', compute_type='int8', download_root='/app/models') for name in ['small', 'large-v3-turbo']]"
COPY stt_service.py .
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app
EXPOSE 8002
HEALTHCHECK --interval=15s --timeout=3s --start-period=90s --retries=5 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/api/stt/health', timeout=2)"
CMD ["uvicorn", "stt_service:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log"]
