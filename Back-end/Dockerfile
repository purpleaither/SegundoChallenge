FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 ANONYMIZED_TELEMETRY=False VECTOR_DB_PATH=/app/index AUDIO_LIMIT_DB=/app/data/audio_limits.sqlite3
WORKDIR /app
COPY Back-end/requirements.txt /app/Back-end/requirements.txt
COPY sistema_multiagente/requirements.txt /app/sistema_multiagente/requirements.txt
RUN pip install -r /app/Back-end/requirements.txt
COPY sistema_multiagente /app/sistema_multiagente
COPY Back-end /app/Back-end
COPY Dados-RAG /app/Dados-RAG
RUN useradd --create-home --uid 1000 app && mkdir -p /app/index /app/data && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=600s --retries=5 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["sh", "-c", "python Back-end/bootstrap.py && exec uvicorn main:app --app-dir Back-end --host 0.0.0.0 --port 8000 --no-access-log"]
