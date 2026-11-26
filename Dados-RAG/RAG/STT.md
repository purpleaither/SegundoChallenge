# STT local do GuIA Social

Este serviço fica em `Dados-RAG/RAG` com o restante do código RAG. O front-end
grava áudio com `MediaRecorder` e envia um arquivo WebM/Opus, MP4,
Ogg ou WAV ao servidor local. O servidor usa faster-whisper em português,
CPU/int8, sem SpeechRecognition e sem chave de API. Depois da instalação e do
download do modelo, a inferência é local.

## Instalação (Python 3.12)

A partir de `Dados-RAG/RAG`:

```sh
python3.12 -m venv .venv-stt
.venv-stt/bin/pip install -r requirements-stt.txt
.venv-stt/bin/python -c "from faster_whisper import WhisperModel; [WhisperModel(name, device='cpu', compute_type='int8', download_root='models-stt') for name in ['small', 'large-v3-turbo']]"
STT_MODEL_DIR="$PWD/models-stt" .venv-stt/bin/uvicorn stt_service:app --host 127.0.0.1 --port 8002 --no-access-log
```

`STT_MODEL` configura a revisão final (padrão: large-v3-turbo);
`STT_PREVIEW_MODEL` configura as prévias (padrão: small). Ambos devem estar instalados.
O serviço só carrega arquivos locais durante a inicialização. No Docker Compose,
o modelo é baixado na construção da imagem, e o frontend aguarda o healthcheck.
`STT_URL` configura o destino do proxy Next (padrão http://127.0.0.1:8002);
reinicie/recompile o frontend após alterar esse endereço.

O cache `models-stt/` na raiz do repositório contém somente um snapshot
`large-v3-turbo` do Mobius Labs e não é usado pelos comandos padrão: eles usam
`Dados-RAG/RAG/models-stt` ou baixam os modelos durante a construção do Docker.
Não remova o cache versionado sem confirmar se há um fluxo local que dependa dele.

## Fluxo e limites

1. Ao iniciar a gravação, o navegador pede permissão para usar o microfone e
   interrompe uma leitura TTS em andamento.
2. Ao parar (ou atingir 60 segundos), o front-end envia uma gravação para
   `POST /api/stt`. A interface não envia prévias enquanto a pessoa fala.
3. O retorno `{"text":"...","language":"pt-BR"}` preenche o campo editável; a
   pergunta só é enviada ao assistente quando a pessoa confirma o envio.
4. O limite do serviço é 60 segundos e 8 MiB. A pergunta final respeita 1.000
   caracteres. A requisição tem timeout de 90 segundos; se falhar, a interface
   informa o erro e mantém qualquer texto digitado no campo.

O endpoint também aceita WebM/Opus, MP4, Ogg e WAV para clientes que enviam arquivos.
O parâmetro `preview=true` continua disponível no serviço, mas o front-end atual
não o utiliza.

O áudio fica em memória; o serviço não persiste gravações nem registra seu conteúdo.
Navegação/nova conversa/desmontagem cancela o envio em andamento e descarta resultados
atrasados. Uma inferência que já começou no servidor pode terminar mesmo após o
cancelamento do cliente. O modelo permanece no disco, mas não o áudio recebido.

HTTPS (ou localhost), permissão de microfone e suporte a AudioContext/AudioWorklet são necessários.
Sem suporte, a digitação continua disponível. As prévias são incrementais, com revisões e atraso de processamento: não é
streaming palavra por palavra. O histórico completo (até 60 s) é reprocessado a cada
prévia para preservar contexto; isso aumenta o custo computacional em falas longas.
O endpoint permite uma inferência por processo e retorna 429 quando ocupado; não faz fila.

GET `/api/stt/health` verifica prontidão. Erros: 413 (limite), 415 (formato),
422 (áudio inválido/vazio), 429 (ocupado), 503 (indisponível).
Antes de expor publicamente, aplicar autenticação/limitação de tráfego e proteção de
corpos nos logs do proxy. Qualidade com sotaques, ruído e latência sob carga precisam
de avaliação com falas reais; um teste sintético não comprova esses requisitos.

## Testes

```sh
.venv-stt/bin/pip install httpx2
.venv-stt/bin/python -m unittest test_stt_service.py
```

No Windows, use os comandos de
[Como_executar_win.md](../../Como_executar_win.md).

Frontend: `node --experimental-strip-types --test lib/*.test.mjs`.

Referências: [faster-whisper e licença MIT](https://github.com/SYSTRAN/faster-whisper),
[modelo small convertido](https://huggingface.co/Systran/faster-whisper-small),
[modelo turbo convertido](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo),
[Whisper e licença MIT](https://github.com/openai/whisper).
