# Front-end

Interface de chat criada com Next.js, React e TypeScript. A página principal
está em `app/page.tsx`, os estilos em `app/globals.css` e as chamadas HTTP em
`lib/api.ts`.

## Executar localmente

Requer Node.js e npm. Na pasta `Front-end`:

```powershell
npm ci
npm run dev
```

Abra `http://localhost:3000`. Para apontar o proxy do Next.js para outro
endereço da API, configure `BACKEND_URL` em `Front-end/.env.local`:

```text
BACKEND_URL=http://127.0.0.1:8000
```

O proxy encaminha as rotas `/api/*` para esse endereço. O padrão é
`http://127.0.0.1:8000`.

## Integração com a API

Atualmente, `lib/api.ts` envia `POST /api/perguntar` com `{ "pergunta": "..." }`
e espera uma resposta com `resposta` e `programas`. A API FastAPI em
`Back-end/main.py` ainda expõe outro contrato, incluindo `POST /api/chat`, que
recebe `question` e retorna `answer` e `citations`. Portanto, o contrato do
chat do front-end ainda precisa ser alinhado ao back-end para que a conversa
funcione integrada.

## Verificações

```powershell
npm run typecheck
npm run build
```