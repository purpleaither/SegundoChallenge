# 🏡 Assistente virtual de benefícios sociais 🏡

## Descrição do projeto ✏️

O chatbot Assistente Virtual de Benefícios Sociais é um assistente informativo para ajudar cidadãos a
encontrar programas sociais potencialmente relacionados à sua atual situação. A aplicação consulta uma base
estruturada de programas e documentos oficiais, recupera trechos relevantes e apresenta informações com 
referências.

> **Observação:** A resposta obtida não é uma confirmação de elegibilidade nem substituem a avaliação do órgão
responsável. A base pode conter critérios parciais ou que estão fora do escopo desejado, portanto, confirme
sempre as regras e os procedimentos nas fontes oficiais. 

## Visão geral 👀

- Base de conhecimento: 42 programas federais descritos em um arquivo CSV.
- Documentos de apoio: Fichas Markdown derivadas do CSV e textos legislativos oficiais.
- RAG: Embeddings multilíngues `bge-m3`, gerados localmente pelo Ollama, com armazenamento vetorial ChromaDB.
- API: Python, FastAPI e Pydantic.
- Interface: Next.js 16, React 19 e TypeScript.
- Persistência: Índice ChromaDB local e API usando SQLite para controlar a cota de tentativas de áudio por conversa.

## Arquitetura adotada (RAG x LLM) 🏗️

A arquitetura de recuperação e resposta está descrita em semana03-simplificacao.md. A configuração adotada evita
usar um LLM para redigir as respostas de produção, e o texto é montado a partir dos campos recuperados da base.

<div align="center">
  <img width="581" height="703" alt="diagrama" src="https://github.com/user-attachments/assets/70759542-bd6d-4943-bed0-7ec84d981b95" />
</div>

### Fluxo de consulta:
1. Pergunta enviada chega na API.
2. O módulo `Dados-RAG/RAG/rag.py` expande algumas expressões populares utilizadas no DF, e gera o embedding
da pergunta com `bge-m3`.
3. O ChromaDB recupera os trechos mais próximos por similaridade vetorial.
4. O limiar `RAG_MIN_SIMILARITY` controla quando a aplicação deve se abster de responder por falta de contexto
suficiente.
5. `compose_answer()` monta uma resposta determinística com os dados recuperados e a API retorna as fontes/citações
disponíveis.

> O limiar padrão `0.532` foi mantido após uma validação estratificada (20 casos para ajuste, 7 para holdout; seed 42): deixou passar as 21 consultas em escopo e filtrou as 6 fora de escopo. No holdout, classificou as 7 corretamente. A amostra é pequena e curada; isso não garante precisão nem substitui validação com perguntas independentes quando a base ou o modelo mudar.

## Organização dos arquivos 🧱

```text
|
├── Back-end/
│   ├── main.py                 # API FastAPI principal
│   ├── requirements.txt        # Dependências Python da API
│   └── test_main.py            # Testes do back-end
├── Front-end/
│   ├── app/                    # Páginas, layout e estilos Next.js
│   ├── lib/api.ts              # Cliente HTTP usado pela interface
│   ├── package.json            # Scripts e dependências Node
│   ├── next.config.mjs         # Proxy /api para a API Python
│   └── Dockerfile
├── Dados-RAG/
│   ├── programas_sociais_legislacao_links_oficiais.csv
│   └── RAG/
│       ├── base/               # 42 fichas Markdown derivadas do CSV
│       ├── fontes/             # Textos oficiais baixados
│       ├── avaliacao/          # Casos, amostras e resultados de avaliação
│       ├── resultados/         # Resultados dos experimentos anteriores
│       ├── dataset.py          # Leitura, validação e preparação da base
│       ├── fontes.py           # Download e leitura de fontes oficiais
│       ├── baixar_fontes.py    # Coleta dos documentos oficiais
│       ├── ingestao.py         # Geração de embeddings e indexação
│       ├── rag.py              # Recuperação e resposta determinística
│       ├── avaliar.py          # Métricas objetivas de recuperação
│       └── testes-automatizados/ # Testes unitários e instruções
├── Documentos/                 # Relatórios e documentação do projeto
├── .github/workflows/          # Automação de release
├── docker-compose.yml
└── README.md
```

- `Back-end/`: API FastAPI e testes do servidor.
- `Front-end/`: Interface web em Next.js, React e TypeScript.
- `Front-end/app/`: Tela principal do chat, responsável por enviar perguntas à API, atualizar a conversa e apresentar respostas e fontes.
- `Dados-RAG/`: Dados da aplicação, incluindo o CSV dos programas e os módulos Python do RAG. No Windows, o índice vetorial fica por padrão em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3`, fora do repositório.
- `Dados-RAG/programas_sociais_legislacao_links_oficiais.csv`: base estruturada dos 42 programas.
- `Dados-RAG/RAG/`: preparação dos dados, ingestão, recuperação, respostas determinísticas, avaliação RAGAS e testes.
- `Dados-RAG/RAG/base/`: fichas Markdown derivadas do CSV.
- `Dados-RAG/RAG/fontes/`: textos legislativos oficiais baixados.
- `Dados-RAG/RAG/testes-automatizados/`: Testes unitários e script `executar_testes.py`, que também inicia a avaliação RAGAS integrada.
- `Dados-RAG/RAG/avaliacao/`: Casos versionados do teste integrado RAG + RAGAS; os resultados são gerados ao executar a avaliação.
- `Dados-RAG/__init__.py`: Arquivo Python que identifica Dados como pacote e contém uma breve descrição. Em algumas versões do Python, os diretórios podem ser importados sem ele, mas mantemos para deixar explícita a estrutura do pacote.
- `Como_executar_win.md`: Comandos do Windows para instalar dependências, iniciar os serviços, testar respostas e executar a avaliação.
- `models-stt/`: Cache LFS versionado de `large-v3-turbo` (~1,6 GB). Os scripts atuais não o usam: a execução local usa `Dados-RAG/RAG/models-stt` e o Docker baixa os modelos no build.
- `__pycache__/`: Pasta criada automaticamente pelo Python para guardar bytecode compilado (.pyc) e acelerar importações futuras. 
- `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3`: Banco vetorial persistente do ChromaDB no Windows. É derivado dos dados e recriável com script de ingestão.
- `Documentos/`: Relatórios e documentos do projeto.

## Instalação e execução no Windows 💻

### 1. Pré-requisitos
- Python 3.12.
- Node.js compatível com o projeto (o Dockerfile usa Node 24 e npm).
- Ollama instalado e em execução.
- Modelo de embeddings `bge-m3` disponível no Ollama.
- Windows PowerShell que podem ser adaptados de acordo com o Sistema Operacional.

```powershell
ollama pull bge-m3
```

### 2. Preparação do ambiente
Esses comandos devem ser executados na raiz do repositório.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\Back-end\requirements.txt
```

As dependências do RAG e o ChromaDB são declaradas em `Dados-RAG/RAG/requirements.txt`. O arquivo `Back-end/requirements.txt`
instala FastAPI, Uvicorn e ChromaDB para a API principal; use o arquivo do RAG caso queira preparar um ambiente
dedicado para esses módulos:

```powershell
python -m pip install -r .\Dados-RAG\RAG\requirements.txt
```

### 3. Baixar ou atualizar fontes oficiais

O script lê os endereços da base, baixa documentos de domínios oficiais HTTPS (gov ou leg) e salva os textos em `Dados-
RAG/RAG/fontes/`. Se alguma fonte estiver indisponível, o script informa a falha, e essa preparação exige o mínimo de 
documentos que foi definido em `fontes.py`.

```powershell
python .\Dados-RAG\RAG\baixar_fontes.py
```

### 4. Criar ou atualizar índice vetorial

Antes de rodar o próximo comando confirme que o Ollama está ativo e que `bge-m3` foi baixado.

```powershell
python .\Dados-RAG\RAG\ingestao.py
```

A ingestão válida o CSV, prepara trechos das fichas dos programas e das fontes legislativas, calcula embeddings em lotes
e recria a coleção do ChromaDB. Execute novamente caso altere o CSV, documentos de origem, modelo de embeddings ou lógica
de chunking.

O caminho do banco vetorial pode ser configurado pela variável `VECTOR_DB_PATH`. Sem essa variável, o código usa 
`%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3` no Windows quando LOCALAPPDATA está definido, em outros casos usa `Dados-RAG/
vetor-v3`.

### 5. Iniciar a API

A API ficará disponível em http://127.0.0.1:8000.

```powershell
python -m uvicorn main:app --reload --app-dir .\Back-end
```

> A API usa o índice criado na etapa anterior. Se o Ollama estiver indisponível ou o índice não puder ser consultado, a API
poderá retornar erro de serviço indisponível.

### 6. Iniciar o Front-end

A interface ficará disponível em http://localhost:3000. O Next.js encaminha as requisições `/api/*` para `BACKEND_URL`, 
definido em `Front-end/next.config.mjs`. Por padrão, o destino é `http://127.0.0.1:8000`.

```powershell
cd .\Front-end
npm ci
npm run dev
```

## Testes 🧩

Os testes unitários cobrem o back-end, o sistema multiagente e o RAG. Eles não exigem Ollama em execução, índice vetorial previamente
criado ou uma chave de API.

```powershell
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py
```

## Limitações conhecidas 🚧
- A base contém 42 programas federais; não representa um catálogo completo de benefícios estaduais, municipais ou específicos do Distrito Federal.
- A presença de um programa nos resultados não significa que a pessoa cumpre seus critérios.
- Alguns critérios estão parciais ou não foram especificados na base. A resposta deve preservar essa incerteza e encaminhar a pessoa à fonte ou ao órgão responsável.
- Similaridade vetorial não é uma classificação infalível de intenção. Perguntas válidas podem não recuperar contexto suficiente e perguntas fora do escopo podem se aproximar semanticamente de documentos da base.
- A validação estratificada (20 casos para ajuste, 7 para holdout; seed 42) manteve o limiar 0.532: 21/21 consultas em escopo passaram pelo limiar e 6/6 fora de escopo foram filtradas; o holdout foi classificado corretamente. Essa amostra curada é limitada; use perguntas independentes para futuras recalibrações.
- Os resultados experimentais e de avaliação são fotografias de conjuntos específicos; não são garantia de desempenho futuro nem de atualização normativa.

## Multimodalidade: texto e áudio 🎙️

O assistente admite entrada por texto e voz em português:

- Entrada textual no campo de conversa;
- Entrada por voz gravada por até 60 segundos no navegador com `MediaRecorder`;
- Transcrição local com Whisper (`POST /api/stt`), colocada no campo para revisão;
- Leitura opcional das respostas com Piper local (`POST /api/tts`);
- Citações oficiais exibidas junto à resposta.

Depois da revisão, a pergunta segue por `POST /api/orientar`. Nenhum áudio é enviado
ao Gemini ou gravado em disco. `/api/audio/*` e `/api/chat` são rotas legadas de
referência; a interface atual não as chama e a cota antiga não limita o STT.
Consulte [multimodalidade/README.md](multimodalidade/README.md) para o fluxo completo.

## Colaboradores ♟️

<table>
  <tr>
    <td align="center" valign="top">
      <a href="https://github.com/anagiulias">
        <img src="https://github.com/anagiulias.png?size=120" width="100" />
      </a>
      <br />
      <strong>GIULIO SANTOS</strong>
      <br />
      <a href="https://github.com/anagiulias">@Giulio</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/IanLucca12">
        <img src="https://github.com/IanLucca12.png?size=120" width="100" />
      </a>
      <br />
      <strong>IAN MESQUITA</strong>
      <br />
      <a href="https://github.com/IanLucca12">@IanLucca12</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/idelmondez">
        <img src="https://github.com/idelmondez.png?size=120" width="100" />
      </a>
      <br />
      <strong>IVAN OLIVEIRA</strong>
      <br />
      <a href="https://github.com/idelmondez">@idelmondez</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/volktz">
        <img src="https://github.com/volktz.png?size=120" width="100" />
      </a>
      <br />
      <strong>PAULO SILVA</strong>
      <br />
      <a href="https://github.com/volktz">@volktz</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/purpleaither">
        <img src="https://github.com/purpleaither.png?size=120" width="100" />
      </a>
      <br />
      <strong>THAYNA DUTRA</strong>
      <br />
      <a href="https://github.com/purpleaither">@purpleaither</a>
    </td>
  </tr>
</table>
