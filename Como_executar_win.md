# Como executar o projeto no Windows

Este passo a passo vale quando o projeto foi baixado como ZIP pelo GitHub e ainda não está configurado em um ambiente virtual.

> **Dica:** Para todos os passos abaixo, recomendamos usar o **PowerShell** (ou o Terminal do Windows) e manter cada serviço rodando em uma aba/janela separada.

---

## 1. Instalar ferramentas

Você pode instalar as ferramentas via **winget** (gerenciador nativo do Windows 10/11) ou pelos instaladores oficiais:

### Opção A: Instalação rápida via PowerShell (winget)

Abra o **PowerShell** e execute:

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install Ollama.Ollama
```

*(Após a instalação, feche e abra o PowerShell novamente para atualizar as variáveis de ambiente).*

### Opção B: Instaladores manuais
- **Python 3.12:** Baixe em [python.org](https://www.python.org/downloads/) (**importante:** marque a opção *"Add python.exe to PATH"* na primeira tela do instalador).
- **Node.js (LTS):** Baixe em [nodejs.org](https://nodejs.org/).
- **Ollama:** Baixe em [ollama.com](https://ollama.com/download/windows).

### Configurar o Ollama e baixar o modelo

Abra o aplicativo **Ollama** pelo Menu Iniciar (ele ficará ativo na bandeja do sistema, perto do relógio) ou execute no PowerShell:

```powershell
ollama serve
```

Em uma nova aba do PowerShell, baixe o modelo de embeddings:

```powershell
ollama pull bge-m3
```

---

## 2. Abrir o projeto

1. Se ainda não tiver baixado o projeto, extraia o ZIP.
2. Abra o **PowerShell** e navegue até a pasta do projeto:

```powershell
Set-Location -LiteralPath 'D:\Documentos\Códigos IA\SegundoChallenge-main'
```

Confira se a pasta atual contém `Back-end`, `Front-end`, `Dados-RAG` e `multimodalidade`.

---

## 3. Criar o ambiente Python

Na raiz do projeto, crie e ative o ambiente virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> **Erro de política de execução no PowerShell?** Se aparecer uma mensagem dizendo que a execução de scripts foi desabilitada, execute o comando abaixo e tente ativar novamente:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

Com o `(.venv)` visível no início da linha do terminal, instale as dependências:

```powershell
python -m pip install --upgrade pip
python -m pip install -r Back-end\requirements.txt
```

As dependências de FastAPI, Uvicorn e ChromaDB do RAG já são instaladas pelo
arquivo `Back-end\requirements.txt`; não é necessário instalar outra lista.

### Configurar o provedor do bot (obrigatório)

A conversa usa o Gemini por padrão e precisa de uma chave de API. Alternativamente,
é possível usar um modelo de chat local pelo Ollama. O modelo `bge-m3` instalado
acima serve para embeddings do RAG; ele não gera as respostas do bot.

**Opção A — Gemini:** obtenha uma chave no
[Google AI Studio](https://aistudio.google.com/apikey). Na raiz do projeto, crie
o arquivo `.env` a partir do exemplo (se ainda não existir) e abra-o:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

No `.env`, preencha `GOOGLE_API_KEY` com sua chave, sem aspas:

```text
GOOGLE_API_KEY=sua_chave
```

**Opção B — Ollama local, sem chave de API:** em um terminal com o Ollama ativo,
baixe o modelo de chat:

```powershell
ollama pull qwen2.5:7b
```

No `.env` da raiz, deixe `GOOGLE_API_KEY` vazio e configure:

```text
LLM_FALLBACK_ORDER=ollama
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
```

Não compartilhe nem envie sua chave no chat. O `.env` é local; após criá-lo ou
alterá-lo, reinicie a janela do back-end para carregar a configuração.

---

## 4. Criar o índice de busca (RAG)

Com o Ollama em execução em segundo plano, rode:

```powershell
python Dados-RAG\RAG\ingestao.py
```

Esse procedimento precisa ser repetido somente quando o CSV, as fontes ou o modelo de embeddings forem alterados.

---

## 5. Iniciar a API (Back-end)

Abra uma **nova aba/janela do PowerShell**, entre na raiz do projeto e ative o ambiente:

```powershell
Set-Location -LiteralPath 'D:\Documentos\Códigos IA\SegundoChallenge-main'
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --app-dir Back-end
```

A API ficará disponível em `http://127.0.0.1:8000`. Deixe essa janela aberta.
Confirme que iniciou corretamente abrindo `http://127.0.0.1:8000/api/health`;
deve retornar `{"status":"ok"}`. A documentação da API fica em
`http://127.0.0.1:8000/docs`. Confira também
`http://127.0.0.1:8000/api/assistant/status`; o campo `configured` deve ser
`true` quando a chave ou o provedor local estiver configurado.

---

## 6. Preparar e iniciar os serviços de áudio

Whisper (STT) e Piper (TTS) usam ambientes Python separados do back-end. Execute
as seções A e B em **janelas diferentes do PowerShell** e deixe ambas abertas.
Os modelos são baixados apenas na primeira execução. Os comandos usam o caminho
real deste projeto e chamam diretamente o Python de cada ambiente; não é preciso
ativar ambientes nem alterar a política de execução de scripts.

### A. Whisper — transcrição de áudio (porta 8002)

Na janela A, execute:

```powershell
$projectRoot = 'D:\Documentos\Códigos IA\SegundoChallenge-main'
$ragPath = Join-Path $projectRoot 'Dados-RAG\RAG'
$sttPython = Join-Path $ragPath '.venv-stt\Scripts\python.exe'
Set-Location -LiteralPath $ragPath
if (-not (Test-Path $sttPython)) { py -3.12 -m venv .venv-stt }
& $sttPython -m pip install --upgrade pip
& $sttPython -m pip install -r (Join-Path $ragPath 'requirements-stt.txt')
$env:STT_MODEL_DIR = Join-Path $ragPath 'models-stt'
$env:STT_MODEL = 'large-v3-turbo'
$env:STT_PREVIEW_MODEL = 'large-v3-turbo'
& $sttPython -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8', download_root=r'$env:STT_MODEL_DIR')"
& $sttPython -m uvicorn stt_service:app --host 127.0.0.1 --port 8002 --no-access-log
```

O arquivo principal de `large-v3-turbo` tem cerca de 1,6 GB. Na primeira execução,
aguarde o comando de preparação terminar antes de iniciar o Uvicorn; em uma conexão
lenta, o download pode demorar. Se for interrompido, execute novamente a linha do
`WhisperModel` antes de iniciar o serviço.

### B. Piper — síntese de voz (porta 8001)

Na janela B, execute:

```powershell
$projectRoot = 'D:\Documentos\Códigos IA\SegundoChallenge-main'
$ragPath = Join-Path $projectRoot 'Dados-RAG\RAG'
Set-Location -LiteralPath $ragPath
$ttsPython = Join-Path $ragPath '.venv-tts\Scripts\python.exe'
if (-not (Test-Path $ttsPython)) { py -3.12 -m venv .venv-tts }
& $ttsPython -m pip install --upgrade pip
& $ttsPython -m pip install -r (Join-Path $ragPath 'requirements-tts.txt')
& $ttsPython -m piper.download_voices pt_BR-faber-medium --data-dir (Join-Path $ragPath 'voices')
$env:TTS_MODEL_PATH = Join-Path $ragPath 'voices\pt_BR-faber-medium.onnx'
& $ttsPython -m uvicorn tts_service:app --host 127.0.0.1 --port 8001 --no-access-log
```

No Windows, o serviço prepara automaticamente os dados do eSpeak em um caminho
ASCII curto dentro de `%TEMP%`. Se o serviço não iniciar por causa de caracteres
especiais no caminho temporário, configure `TEMP` e `TMP` para uma pasta ASCII
curta com permissão de escrita antes de executar o comando B.

Confirme que `http://127.0.0.1:8002/api/stt/health` e
`http://127.0.0.1:8001/api/tts/health` respondem com `status: ok`.

## 7. Iniciar o Front-end

Abra **outra aba/janela do PowerShell**:

```powershell
Set-Location -LiteralPath 'D:\Documentos\Códigos IA\SegundoChallenge-main\Front-end'
notepad .env.local
```

Salve estes endereços em `.env.local`:

```text
BACKEND_URL=http://127.0.0.1:8000
STT_URL=http://127.0.0.1:8002
TTS_URL=http://127.0.0.1:8001
```

Depois instale as dependências do front-end (uma vez) e inicie o Next:

```powershell
npm ci
npm run dev
```

A interface ficará disponível em `http://localhost:3000`. Deixe essa janela aberta.
O front-end encaminha as chamadas da conversa para `POST /api/orientar` na API
em `http://127.0.0.1:8000`; não acesse a rota `/api/perguntar`.

---

## 8. Demonstrar texto e áudio na interface

Com a API, os serviços de áudio e o front-end ativos, abra `http://localhost:3000`
no Chrome ou Edge.

1. Digite uma pergunta e envie; confira a resposta formatada e as fontes oficiais.
2. Clique no microfone, permita o acesso e faça uma pergunta falada. Clique de novo
   para parar a gravação.
3. Revise ou edite a transcrição no campo de texto e envie-a ao assistente.
4. Na resposta, clique em **Ouvir resposta**; durante a reprodução, o mesmo botão
   permite parar o áudio.
5. Para evidência da entrega, capture a transcrição antes do envio, a resposta
   formatada com fontes e a reprodução iniciada. Não inclua chaves ou dados pessoais.

O áudio é transcrito localmente e não é salvo. A gravação tem limite de 60 segundos;
o navegador precisa de permissão de microfone e a transcrição deve ser revisada.

### Demonstração adicional pelo CLI

Abra uma aba do PowerShell na raiz do projeto:

```powershell
Set-Location -LiteralPath 'D:\Documentos\Códigos IA\SegundoChallenge-main'
.\.venv\Scripts\Activate.ps1
```

Execute os modos de texto, áudio e síntese de voz (`--falar`):

```powershell
# Modalidade Texto
python multimodalidade\demo_multimodal.py "Quais benefícios existem para gestantes?" --modalidade texto

# Modalidade Áudio
python multimodalidade\demo_multimodal.py "Como funciona o Bolsa Família" --modalidade audio

# Modalidade Áudio com leitura em voz alta (TTS no Windows)
python multimodalidade\demo_multimodal.py "Quais critérios para o BPC" --modalidade audio --falar
```

## 9. Executar testes automatizados

Com o ambiente virtual ativado na raiz do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest Back-end\test_main.py
python Dados-RAG\RAG\testes-automatizados\executar_testes.py
Push-Location Dados-RAG\RAG
.\.venv-stt\Scripts\python.exe -m pip install httpx2
.\.venv-stt\Scripts\python.exe -m unittest test_stt_service.py
.\.venv-tts\Scripts\python.exe -m pip install httpx2
.\.venv-tts\Scripts\python.exe -m unittest test_tts_service.py
Pop-Location
Push-Location Front-end
npm test
npm run typecheck
npm run build
Pop-Location
```

---

## Opção alternativa: Executar tudo via Docker

Se você tiver o **Docker Desktop for Windows** instalado e em execução (com WSL2 habilitado):

```powershell
Set-Location -LiteralPath 'D:\Documentos\Códigos IA\SegundoChallenge-main'
docker compose up --build
```

Acesse `http://localhost:3000`. Na primeira execução, os contêineres baixam os
modelos do Ollama, Whisper e Piper; a criação do índice pode levar alguns minutos.

---

## Problemas comuns no Windows

- **Erro `Activate.ps1 cannot be loaded because running scripts is disabled`:** Execute `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` no PowerShell e confirme com `S`.
- **Comando `python` ou `py` não reconhecido:** Reinstale o Python marcando **"Add python.exe to PATH"** ou desative os aliases de instalador da Microsoft Store em *Configurações > Aplicativos > Configurações avançadas de aplicativo > Aliases de execução de aplicativo* (desmarque `python.exe` e `python3.exe`).
- **Microfone bloqueado no Windows:** Vá em **Configurações > Privacidade e segurança > Microfone**, ative o *Acesso ao microfone* e garanta que a opção *Permitir que aplicativos da área de trabalho acessem seu microfone* esteja ativada.
- **Porta 8000 ocupada:** Inicie a API em outra porta (`python -m uvicorn main:app --reload --app-dir Back-end --port 8001`) e crie `Front-end\.env.local` com `BACKEND_URL=http://127.0.0.1:8001`. Reinicie `npm run dev` após alterar essa variável.
- **Porta 3000 ocupada:** Inicie o front-end com `npm run dev -- --port 3001`; a API continua na porta 8000. A interface ficará em `http://localhost:3001`.
- **“Assistente indisponível. A configuração do serviço precisa ser concluída.”:** Configure a opção Gemini ou Ollama no passo 3, reinicie o back-end e confirme `configured: true` em `/api/assistant/status`. Para Ollama, confirme também que o serviço está ativo e que `qwen2.5:7b` foi baixado.
- **Ollama indisponível:** Verifique se o ícone do Ollama está na bandeja do sistema (perto do relógio) ou execute `ollama serve` e confirme com `ollama list`.
- **Modelo ausente:** Execute `ollama pull bge-m3`.
- **Índice vazio:** Execute `python Dados-RAG\RAG\ingestao.py` com o Ollama ativo.

---

## Segurança e limites

- A entrada por voz usa até **10 reservas por conversa a cada 24 horas**.
- A entrada por texto **não** consome essa cota.
- Não envie dados pessoais, números de documentos (CPF, NIS) ou dados bancários.
- A resposta tem caráter estritamente orientativo e não confirma elegibilidade oficial.