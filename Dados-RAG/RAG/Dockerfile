# API RAG determinística (Dados-RAG/RAG/api.py)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuário sem privilégios; chroma_db/ fica num volume gravável por ele
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/chroma_db \
    && chown -R app:app /app
USER app

EXPOSE 8000

# start-period longo: na primeira subida a API indexa a base no bge-m3 (CPU) antes de responder
HEALTHCHECK --interval=10s --timeout=3s --start-period=600s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/saude', timeout=2)"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]