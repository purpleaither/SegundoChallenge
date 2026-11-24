# Front-end

Interface de chat criada com Next.js, React e TypeScript. A página principal
está em `app/page.tsx`, os estilos em `app/globals.css` e as chamadas HTTP em
`lib/api.ts`.

## Executar localmente

Requer Node.js e npm. Para o fluxo completo de texto e áudio, inicie também a
API principal e os serviços locais STT/Whisper e TTS/Piper descritos no
[guia Windows](../Como_executar_win.md). Na pasta `Front-end`, crie ou edite
`.env.local`:

```powershell
BACKEND_URL=http://127.0.0.1:8000
STT_URL=http://127.0.0.1:8002
TTS_URL=http://127.0.0.1:8001
```

Depois execute:

```powershell
npm ci
npm run dev
```

Abra `http://localhost:3000`. Reinicie o Next após alterar `.env.local`.

## Integração com a API

`lib/api.ts` envia `POST /api/orientar` com `{ "question": "..." }` e consome
o contrato `answer`, `benefits`, `sources`, `support_message` e `notice` da API
FastAPI. O Next encaminha a transcrição em `POST /api/stt` ao Whisper local e
`POST /api/tts` ao Piper, mantendo todas as chamadas na mesma origem do navegador.
O áudio gravado é transcrito antes de ser enviado ao assistente; o texto pode ser
revisado e editado. A resposta é renderizada como Markdown e pode ser ouvida por
solicitação do usuário.

```text
BACKEND_URL=http://127.0.0.1:8000
STT_URL=http://127.0.0.1:8002
TTS_URL=http://127.0.0.1:8001
```

### Limitações e falhas conhecidas

- Áudio de até 60 segundos e 8 MiB; a transcrição não é incremental. O usuário
  deve parar a gravação, revisar o texto e enviar a pergunta.
- A gravação exige permissão do microfone e navegador compatível em HTTPS ou
  `localhost`. Sem isso, o campo de texto continua disponível.
- O áudio é processado pelo Whisper local em CPU e não é persistido. A resposta
  escrita (não o áudio) é enviada à API principal.
- STT/TTS indisponíveis ou ocupados retornam erro visível para permitir nova
  tentativa. Confirme `/api/stt/health` na porta 8002 e `/api/tts/health` na
  porta 8001. Vozes longas são divididas em trechos, podendo haver pausas.
- O leitor não inicia automaticamente; use **Ouvir resposta**. PDF, imagem e
  vídeo não são suportados nesta entrega.

## Verificações

```powershell
npm test
npm run typecheck
npm run build
```