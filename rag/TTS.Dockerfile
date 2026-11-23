FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-tts.txt .
RUN pip install -r requirements-tts.txt
RUN python -m piper.download_voices pt_BR-faber-medium --data-dir /app/voices
COPY tts_service.py .
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/tts/health', timeout=2)"
CMD ["uvicorn", "tts_service:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
