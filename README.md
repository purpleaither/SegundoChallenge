# Assistente Virtual do DF

Chatbot institucional que ajuda moradores do Distrito Federal a encontrar programas sociais potencialmente relacionados à sua situação. A resposta é informativa, usa trechos recuperados da base e cita fontes; não decide elegibilidade.

## Base de conhecimento e RAG

A base atual parte de `Dados/programas_sociais_legislacao_links_oficiais.csv`, com 42 programas federais, e indexa também os textos legislativos integrais baixados dos links oficiais da planilha. Na coleta desta revisão, 27 textos HTML oficiais foram validados e indexados; dois links servem PDFs que o coletor ainda não extrai e uma página retornou erro temporário. Os critérios da planilha continuam parciais em vários programas, e o catálogo não cobre todos os benefícios do DF. A implementação, estratégia de chunking e embeddings, arquitetura e limitações estão documentadas em [Dados/rag/README.md](Dados/rag/README.md).

O histórico das alterações no RAG, no índice vetorial e na interface está em [Dados/rag/readme-alteracoes.md](Dados/rag/readme-alteracoes.md).

O documento [Documentacao/semana_2.md](Documentacao/semana_2.md) relaciona a implementação aos requisitos do segundo desafio, descreve a arquitetura e registra os resultados reais da busca, da avaliação de recuperação e da API.

## Pastas e arquivos do projeto

| Nome | O que significa e para que serve |
|---|---|
| `Back-end/` | Código Python do servidor. `main.py` define a API que recebe perguntas e conversa com o RAG. |
| `Front-end/` | Arquivos da interface aberta no navegador: HTML define o conteúdo, CSS a aparência e JavaScript o comportamento. |
| [`Front-end/app.js`](Front-end/app.js) | JavaScript da tela principal do chat: envia perguntas à API, atualiza a conversa e apresenta respostas e fontes. O sufixo `.js` identifica um arquivo JavaScript. |
| `Dados/` | Dados usados pela aplicação, incluindo o CSV dos programas e os módulos Python do RAG. No Windows, o índice vetorial fica por padrão fora do repositório, em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`. |
| `Dados/rag/` | Implementação única do RAG em uso pela API: preparação da base, ingestão, busca, verificação semântica de escopo, respostas e avaliação RAGAS. |
| `Dados/rag/testes-automatizados/` | Testes unitários e script `executar_testes.py`, que também inicia a bateria RAGAS integrada. |
| `Dados/rag/avaliacao/` | Casos versionados do teste integrado RAG + RAGAS; os resultados locais são gerados ao executar a avaliação. |
| `Dados/rag-ragas/` | Protótipo experimental antigo preservado como histórico; não é usado pelo back-end. A avaliação atual fica em `Dados/rag/`. |
| `terminal.txt` | Comandos PowerShell para instalar dependências, iniciar o Ollama, testar respostas, rodar testes automáticos e avaliar com RAGAS. |
| `Dados/rag/base/` | Arquivos Markdown gerados a partir dos registros do CSV. São documentos derivados para o pipeline, não 42 fontes originais independentes. |
| [`Dados/__init__.py`](Dados/__init__.py) | Arquivo Python que identifica `Dados` como pacote e contém uma breve descrição. Em versões modernas do Python, alguns diretórios podem ser importados sem ele, mas mantê-lo deixa explícita a estrutura do pacote e é convencional. |
| `__pycache__/` | Pasta criada automaticamente pelo Python para guardar bytecode compilado (`.pyc`) e acelerar importações futuras. Não é código-fonte nem precisa ser enviada; o Python a recria quando necessário. O Git a ignora. |
| `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2` | Banco vetorial persistente do ChromaDB no Windows. É derivado dos dados e recriável com o script de ingestão. |
| `Back-end/requirements.txt` | Lista as bibliotecas Python usadas pelo servidor e pelo RAG. O comando `pip install -r` instala essas dependências no ambiente Python; não instala o Ollama nem baixa os modelos de IA. |
| `Dados/rag/requirements.txt` | Lista de dependências Python para o módulo RAG quando tratado separadamente. Para executar o projeto completo, o README usa `Back-end/requirements.txt`. |
| `Dados/rag/requirements-avaliacao.txt` | Dependências opcionais para avaliar respostas com RAGAS e o juiz OpenAI. |
| `.gitignore` | Lista arquivos locais ou gerados que o Git deve ignorar, como ambientes virtuais, caches Python, o índice local e arquivos de configuração com segredos. |
| `Dados/rag/testes-automatizados/test_*.py` | Testes automatizados que verificam partes do código sem precisar demonstrar o sistema pela interface. |

Em resumo: `app.js` é código da interface; `requirements.txt` lista dependências; `__init__.py` ajuda a organizar/importar módulos Python; `__pycache__/` é cache descartável; e `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2` guarda o índice local usado para buscar trechos relevantes no Windows.

## Executar no Windows

Crie o ambiente Python e instale as dependências:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Back-end\requirements.txt
```

Use Python 3.12 para este fluxo se a instalação do ChromaDB falhar por falta de uma versão compatível do `onnxruntime`.

Configure uma chave da OpenAI para a classificação e geração de respostas e instale o [Ollama](https://ollama.com/) para os embeddings:

```powershell
$env:OPENAI_API_KEY = "sua-chave"
ollama pull bge-m3
```

Baixe/atualize os textos legislativos e gere o índice depois de alterar o CSV ou as fontes:

```powershell
python .\Dados\rag\baixar_fontes.py
python .\Dados\rag\ingestao.py
```

Inicie a API:

```powershell
python -m uvicorn main:app --reload --app-dir .\Back-end
```

Em outro terminal, sirva a interface e abra `http://127.0.0.1:5500/`:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory .\Front-end
```

A documentação da API fica em `http://127.0.0.1:8000/docs`. No Windows, o índice vetorial é gravado por padrão em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`; o controle de tentativas de voz fica em `Back-end/data/audio_limits.sqlite3`. Ambos são locais. O índice foi movido para fora do caminho do repositório porque a pasta do projeto contém caracteres acentuados e o ChromaDB não persistiu seus arquivos HNSW nesse caminho. `VECTOR_DB_PATH`, `OLLAMA_URL`, `OLLAMA_EMBEDDING_MODEL`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` e `RAG_MAX_DISTANCE` podem ser configurados por variáveis de ambiente; no Windows, configure `VECTOR_DB_PATH` para um caminho sem caracteres acentuados.

Também é possível demonstrar a recuperação sem abrir a interface:

```powershell
python .\Dados\rag\buscar.py "Tem ajuda para comprar o botijão de gás?"
python .\Dados\rag\buscar.py --responder "Como faço para não pagar a inscrição do Enem?"
python .\Dados\rag\avaliar.py
```

O modo `--responder` usa a busca, a classificação de escopo e a geração da mesma forma que a API. Para a bateria RAGAS, instale os extras opcionais e rode os testes automatizados integrados:

```powershell
python -m pip install -r .\Dados\rag\requirements-avaliacao.txt
python .\Dados\rag\testes-automatizados\executar_testes.py
```

Por padrão, o script roda os testes unitários e depois os 27 casos da avaliação integrada, fazendo chamadas pagas à OpenAI. Para executar somente os testes locais, use `--apenas-unitarios`; para limitar a bateria, use `--limite 2`. O avaliador integrado exercita o RAG usado pela API, inclusive o classificador semântico que impede uma palavra coincidente de levar a uma resposta fora de contexto. O antigo experimento em `Dados/rag-ragas/` e seus resultados não representam a implementação atual. Consulte [terminal.txt](terminal.txt) para o roteiro completo de execução no Windows.

## Voz, acessibilidade e privacidade

A interface permite perguntas por texto, reconhecimento de fala em português e leitura da resposta sob solicitação. O reconhecimento pode usar o serviço de voz do navegador. O limite de entrada por voz é de 10 tentativas por conversa a cada 24 horas; não é uma proteção por pessoa. O back-end não persiste histórico, e o navegador envia apenas as últimas mensagens da conversa ativa. Evite informar CPF, endereço ou outros dados pessoais.

O link “Entrar ou criar conta” abre telas de protótipo para login, cadastro e recuperação. Os formulários estão desativados: ainda não há autenticação no back-end, banco de contas nem envio de token por e-mail. Não use dados reais nessas telas.

## Testes

```powershell
python -m unittest discover -s .\Back-end -p "test_*.py"
python -m unittest discover -s .\Dados\rag -p "test_*.py"
```

Validação desta alteração: **13 testes do back-end e 13 testes de dados/fontes passaram**; a verificação de escopo isolada e a sintaxe dos scripts também passaram. A suíte completa do RAG e a bateria RAGAS com Ollama ainda precisam ser executadas em um ambiente com dependências compatíveis e modelos instalados. Neste computador, o Python disponível é 3.15.2 (sem wheel de `onnxruntime` para instalar ChromaDB) e o Ollama está ativo, mas sem modelos; use uma versão Python suportada pelo ChromaDB, como 3.12, e siga os comandos de [terminal.txt](terminal.txt).
