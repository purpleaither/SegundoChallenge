# TTS local do GuIA Social

Este serviço fica em `Dados-RAG/RAG` com o restante do código RAG.
O serviço usa Piper em CPU e a voz `pt_BR-faber-medium`. A fala é ajustada para
`length_scale=1.15`, um pouco mais lenta que o padrão para facilitar o acompanhamento.
Não requer chave de API. Depois de instalar dependências e baixar a voz, a síntese
funciona localmente.

## Executar separadamente do RAG

A partir de `Dados-RAG/RAG`, com Python 3.12:

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

No Windows, o serviço copia os dados do eSpeak para um diretório ASCII curto em
`TEMP` durante a execução. Isso evita falhas do Piper quando o caminho do projeto
contém caracteres acentuados; se `TEMP` e `TMP` não apontarem para um caminho
ASCII curto, configure uma dessas variáveis antes de iniciar o serviço.

## Contrato e reprodução

- `GET /api/tts/health`: prontidão da voz.
- `POST /api/tts`, JSON `{"text":"Olá."}`: WAV mono, 22.050 Hz, PCM 16 bits.
- Texto obrigatório, até 600 caracteres. Entrada inválida: 422; motor ocupado:
  429 com Retry-After; indisponibilidade: 503.
- Uma síntese por processo; o frontend tenta novamente quando recebe 429.
- O front-end divide respostas longas em trechos de até 500 caracteres e solicita
  um WAV por trecho. A reprodução começa somente após clique em **Ouvir resposta**;
  o botão permite parar. Repetir a leitura solicita nova síntese.
- Áudio e texto são processados em memória, sem gravar solicitações em arquivos.
  Respostas usam `Cache-Control: no-store, private`. Configure também os logs do
  proxy de produção para não registrar corpos de solicitações.
- O front-end reproduz os trechos em sequência; pode haver pausas entre eles.
  Não há autoplay, cache de replay ou controles de pausa/continuação.
- Navegação, nova conversa e desmontagem interrompem a leitura. URLs temporárias
  de áudio são revogadas após a reprodução.
- Gravar voz interrompe a leitura; ouvir interrompe a gravação. STT usa
  o serviço local Whisper descrito em [STT.md](STT.md).

Isto é reprodução incremental de WAVs, com possíveis pausas entre trechos; não é
streaming contínuo de bytes nem geração de texto por um LLM. MOS ≥ 4 e o limite de
4 segundos para o primeiro áudio exigem avaliação representativa de qualidade e
carga. O endpoint local não inclui autenticação nem limitação por usuário: antes
de exposição pública, aplicar os mesmos controles de sessão e tráfego do backend.

## Testes

```sh
.venv-tts/bin/pip install httpx2
.venv-tts/bin/python -m unittest test_tts_service.py
```

No Windows, use os comandos de
[Como_executar_win.md](../../Como_executar_win.md).

No frontend: `node --experimental-strip-types --test lib/*.test.mjs`.

## Referências e licenças

- [Piper API Python](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).
- [Motor Piper, GPL-3.0](https://github.com/OHF-Voice/piper1-gpl/blob/main/LICENSE.md).
- [Modelo e ficha da voz](https://huggingface.co/rhasspy/piper-voices/blob/main/pt/pt_BR/faber/medium/MODEL_CARD):
  dataset declarado CC0; a ficha também descreve o modelo base usado no ajuste.
  A licença do dataset não substitui a licença do motor. Preserve os avisos e
  cumpra as condições aplicáveis ao distribuir o serviço.
