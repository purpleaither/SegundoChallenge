# Integração multiagente do GuIA Social

O chat chama `POST /api/orientar` em `Back-end/main.py`. A rota executa o LangGraph
em `sistema_multiagente/graph.py`, incluindo guardrail, seleção de padrão, extrator,
busca, analista, Comunicador, ReWOO, Reflexion e consolidação de apoio do GitHub.
O backend RAG determinístico continua disponível em `/api/assistant` para referência;
a interface não o usa como fallback automático.

## Instalação e execução

Na raiz, com Python 3.12 e Ollama/bge-m3:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r Back-end/requirements.txt
ollama pull bge-m3
.venv/bin/python Back-end/bootstrap.py
.venv/bin/uvicorn main:app --app-dir Back-end --host 127.0.0.1 --port 8000 --no-access-log
```

Inicie `Front-end/` em outro terminal com `npm run dev`. STT e TTS permanecem
independentes nas portas 8002 e 8001, conforme [STT](../Dados-RAG/RAG/STT.md) e
[TTS](../Dados-RAG/RAG/TTS.md).
Docker Compose também inclui o código, as dependências e as variáveis do provedor.

Para chamadas reais ao Gemini, configure `GOOGLE_API_KEY` (ou `GEMINI_API_KEY`) no
ambiente do servidor ou em `.env` da raiz, nunca no frontend nem em NEXT_PUBLIC_.
Há um `.env.example` sem segredos. A configuração não foi preenchida nesta tarefa,
por decisão do usuário. Não há necessidade de compartilhar uma chave no chat.
O fluxo mantém os modelos/tiers configurados no GitHub; sua disponibilidade real
não foi verificada sem credenciais. Reinicie o backend após mudar a configuração.

## Contrato

`POST /api/orientar`, corpo `{"question":"sua pergunta"}`, retorna:

- `answer`: orientação principal, sem duplicar a mensagem de apoio.
- `support_message`: mensagem adicional de apoio/proteção, ou null.
- `speech_text`: mensagem consolidada para a leitura em voz alta.
- `benefits`: somente programas recuperados e aprovados como pertinentes pela análise.
- `sources`: referências dos documentos efetivamente recuperados, independentemente dos cards.
- `notice`, `status`, `execution_pattern`: aviso, resultado e padrão selecionado.

A interface renderiza Markdown sem HTML bruto nem links de protocolos executáveis,
mostra apoio em seção própria, preserva fontes/cards e converte a resposta em texto
falável antes de passá-la ao Piper. Detalhes internos de perfil, prompts e exceções
do provedor não são enviados para a interface.

`GET /api/assistant/status` informa modo multiagente, provedor e presença de
configuração; não faz uma chamada externa nem garante validade da chave/modelos.
`GET /api/health` verifica somente a disponibilidade da API.

Sem credenciais: 503 explícito. Serviço ocupado: 429. A rota possui prazo de 110 s;
se excedido, retorna 504, mas uma chamada síncrona já iniciada pode terminar em segundo
plano e manter o serviço ocupado. Há uma execução por processo. Falha de um agente
pode retornar `status=erro_api` com HTTP 200 quando existe uma saída estruturada,
preservando a mensagem de apoio; isso não é apresentado como sucesso na interface.
Não há fallback silencioso para texto fixo, outro modelo local ou resposta simulada.

## Validação e limites

- 13 testes originais do multiagente passaram sem chamadas ao Gemini.
- 6 testes novos cobrem contrato HTTP, separação de apoio, filtragem de cards,
  credenciais ausentes, ocupado e os três percursos reais do grafo com modelos simulados.
- 44 testes backend/RAG anteriores continuam passando.
- 37 testes frontend passaram, incluindo Markdown seguro, contrato e texto para TTS.
- O proxy local foi verificado: rota multiagente informa 503 sem configuração,
  e API/Piper/Whisper continuam acessíveis.

Os 27 testes RAG determinísticos anteriores não validam a qualidade do multiagente.
Não foram executadas chamadas reais ao Gemini. Não há afirmação de validação clínica,
jurídica ou de elegibilidade. A limitação por UUID/cota de áudio e memória entre
turnos continuam separadas: a rota nova recebe uma mensagem por execução e não
implementa memória persistente nem ativa a reserva de áudio do endpoint `/api/chat`.
