# STT local do GuIA Social

O navegador captura PCM mono com AudioWorklet; o servidor usa faster-whisper em
português, CPU/int8: `small` para prévias e `large-v3-turbo` para a revisão final. Não usa SpeechRecognition
nem requer chave de API. Depois da instalação e do download, a inferência é local.

## Instalação (Python 3.12)

A partir de `rag`:

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

## Fluxo e limites

1. Microfone pede permissão e interrompe a leitura TTS.
2. AudioWorklet captura PCM sem reproduzir o microfone nos alto-falantes. A primeira
   prévia é solicitada após 2,5 segundos de áudio; as seguintes, após mais 2 segundos.
3. Cada prévia envia um WAV independente com o contexto gravado até aquele momento
   para `POST /api/stt?preview=true`. Há no máximo uma requisição por gravação em voo;
   prévias intermediárias são descartadas quando o servidor está processando.
4. A transcrição substitui a prévia anterior, preservando o rascunho original e sem
   duplicar palavras. O usuário vê o texto mudar enquanto fala.
5. Parar libera o microfone, drena o último buffer e pede a revisão final em
   `POST /api/stt`, com modelo maior. O texto fica editável após a conclusão.
6. O retorno é `{"text":"...","language":"pt-BR"}`. Nenhuma pergunta é enviada
   automaticamente. Limites: 60 segundos, 8 MiB e 1.000 caracteres no campo.

O endpoint também aceita WebM/Opus, MP4 e Ogg para clientes que enviam arquivos.
O limite de tempo de cada requisição do frontend é 30 segundos; a finalização inteira
possui limite de 90 segundos. Se falhar, o texto já reconhecido permanece no campo.

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
.venv-stt/bin/pip install httpx
.venv-stt/bin/python -m unittest test_stt_service.py
```

Frontend: `node --experimental-strip-types --test lib/*.test.mjs`.

Referências: [faster-whisper e licença MIT](https://github.com/SYSTRAN/faster-whisper),
[modelo small convertido](https://huggingface.co/Systran/faster-whisper-small),
[modelo turbo convertido](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo),
[Whisper e licença MIT](https://github.com/openai/whisper).
