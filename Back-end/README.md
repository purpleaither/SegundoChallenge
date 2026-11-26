> O chat GuIA Social agora usa o LangGraph via `POST /api/orientar`.
> Veja [configuração, contrato e validação](INTEGRACAO.md).
> `/api/assistant`, `/api/chat` e as rotas de cota de áudio permanecem disponíveis
> como legado e não são chamadas pela interface atual.

# Back-end

API do assistente, implementada com FastAPI. Ela consulta os programas sociais
da base local e usa o RAG em `Dados-RAG/RAG` para recuperar informações e fontes
oficiais. As respostas são informativas e não confirmam elegibilidade.

## Requisitos

- Python 3.12
- Ollama em execução com o modelo de embeddings `bge-m3`

Na raiz do repositório, crie e ative o ambiente virtual e instale as
dependências:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Back-end\requirements.txt
ollama pull bge-m3
```

Baixe as fontes oficiais e gere o índice vetorial antes da primeira consulta:

```powershell
python .\Dados-RAG\RAG\baixar_fontes.py
python .\Dados-RAG\RAG\ingestao.py
```

## Executar

Na raiz do repositório:

```powershell
python -m uvicorn main:app --reload --app-dir .\Back-end
```

Versão em ambiente (.venv):
```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --app-dir .\Back-end
```

A API fica em `http://127.0.0.1:8000`; a documentação interativa do FastAPI
fica em `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /api/health`: Verifica se a API está disponível.
- `GET /api/agencies` e `GET /api/benefits`: Consulta órgãos e programas.
- `POST /api/assistant`: Busca RAG legada, mantida para referência.
- `GET /api/audio/quota` e `POST /api/audio/reserve`: Rotas legadas de consulta e
  reserva de áudio; não limitam o fluxo atual de voz via `/api/stt`.
- `POST /api/chat`: Rota legada de resposta RAG; a interface usa `/api/orientar`.

## Configuração

- `OLLAMA_URL`: Endereço do Ollama; padrão `http://127.0.0.1:11434`.
- `OLLAMA_EMBEDDING_MODEL`: Modelo de embeddings; padrão `bge-m3`.
- `RAG_MIN_SIMILARITY`: Limiar da busca com padrão `0.532`.
- `VECTOR_DB_PATH`: Caminho do índice ChromaDB. No Windows, o padrão é
  `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3`.
- `AUDIO_LIMIT_DB`: Caminho do SQLite usado para os limites de áudio; por
  padrão, `Back-end/data/audio_limits.sqlite3`.

## Testes

Na raiz do repositório, rode os testes do back-end:

```powershell
python -m unittest discover -s .\Back-end -p "test_*.py"
```

Para os testes do back-end e do RAG juntos, use
`python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py`.
