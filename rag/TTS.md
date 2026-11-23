# TTS local do GuIA Social

O serviço usa Piper em CPU e a voz `pt_BR-faber-medium`. Não requer chave de API.
Depois de instalar dependências e baixar a voz, a síntese funciona localmente.

## Executar separadamente do RAG

A partir de `rag`, com Python 3.12:

```sh
python3.12 -m venv .venv-tts
.venv-tts/bin/pip install -r requirements-tts.txt
.venv-tts/bin/python -m piper.download_voices pt_BR-faber-medium --data-dir voices
.venv-tts/bin/uvicorn tts_service:app --host 127.0.0.1 --port 8001 --no-access-log
```

O frontend encaminha `/api/tts` para `http://127.0.0.1:8001` por padrão. Para outro
endereço, defina `TTS_URL` antes de iniciar/compilar o Next. `TTS_MODEL_PATH` permite
usar outro caminho para o arquivo ONNX e seu `.onnx.json` correspondente.

No Docker Compose, `tts` baixa a voz na construção e o frontend espera o serviço
ficar saudável. Reconstrua as imagens após mudar as variáveis de proxy.

## Contrato e reprodução

- `GET /api/tts/health`: prontidão da voz.
- `POST /api/tts`, JSON `{"text":"Olá."}`: WAV mono, 22.050 Hz, PCM 16 bits.
- Texto obrigatório, até 600 caracteres. Entrada inválida: 422; motor ocupado:
  429 com Retry-After; indisponibilidade: 503.
- Uma síntese por processo; o frontend tenta novamente quando recebe 429.
- Áudio e texto são processados em memória, sem gravar solicitações em arquivos.
  Respostas usam `Cache-Control: no-store, private`. Configure também os logs do
  proxy de produção para não registrar corpos de solicitações.
- O player gera trechos de aproximadamente 300 caracteres, antecipa o próximo e
  oferece pausar, continuar, parar e repetir desde o começo. Não há autoplay.
- O replay mantém até 16 MiB de áudio da última resposta em RAM. Navegação, nova
  conversa e desmontagem limpam esse cache. URLs temporárias são revogadas.
- Gravar voz interrompe a leitura; ouvir interrompe a gravação. STT usa
  o serviço local Whisper descrito em [STT.md](STT.md).

Isto é reprodução incremental de WAVs, com possíveis pausas entre trechos; não é
streaming contínuo de bytes nem geração de texto por um LLM. MOS ≥ 4 e o limite de
4 segundos para o primeiro áudio exigem avaliação representativa de qualidade e
carga. O endpoint local não inclui autenticação nem limitação por usuário: antes
de exposição pública, aplicar os mesmos controles de sessão e tráfego do backend.

## Testes

```sh
.venv-tts/bin/pip install httpx
.venv-tts/bin/python -m unittest test_tts_service.py
```

No frontend: `node --experimental-strip-types --test lib/*.test.mjs`.

## Referências e licenças

- [Piper API Python](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).
- [Motor Piper, GPL-3.0](https://github.com/OHF-Voice/piper1-gpl/blob/main/LICENSE.md).
- [Modelo e ficha da voz](https://huggingface.co/rhasspy/piper-voices/blob/main/pt/pt_BR/faber/medium/MODEL_CARD):
  dataset declarado CC0; a ficha também descreve o modelo base usado no ajuste.
  A licença do dataset não substitui a licença do motor. Preserve os avisos e
  cumpra as condições aplicáveis ao distribuir o serviço.
