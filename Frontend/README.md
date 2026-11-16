# Frontend — GovernancIA

Interface de chat em Next.js. As perguntas vão para `/api/perguntar`, que o Next repassa para a
API Python em `rag/api.py` (configuração T5: busca bge-m3 + abstenção + resposta por texto fixo).

## Com Docker (tudo junto)

Na pasta `SegundoChallenge/`:

```bash
docker compose up --build   # abra http://localhost:3000
```

Sobe o Ollama, baixa o `bge-m3` (só na primeira vez), a API em `:8000` e o frontend em `:3000`.

## Sem Docker

1. Backend (em outro terminal, com o Ollama rodando e o modelo `bge-m3` baixado):

   ```bash
   cd SegundoChallenge/rag
   .venv/bin/pip install -r requirements.txt   # uma vez só
   .venv/bin/uvicorn api:app --reload --port 8000
   ```

2. Frontend:

   ```bash
   cd SegundoChallenge/Frontend
   npm install      # uma vez só
   npm run dev      # http://localhost:3000
   ```

Se a API estiver em outro endereço, defina `BACKEND_URL` (padrão: `http://127.0.0.1:8000`).
