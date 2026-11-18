# Frontend — GovernancIA

Interface de chat em Next.js. As perguntas vão para `/api/perguntar`, que o Next repassa para a
API Python em `rag/api.py` (configuração T5: busca bge-m3 + abstenção + resposta por texto fixo).

## Com Docker (tudo junto)

Na pasta `SegundoChallenge/`:

```bash
docker compose up --build   # abra http://localhost:3000
```

Sobe o Ollama, baixa o `bge-m3` (só na primeira vez), a API em `:8000` e o frontend em `:3000`.

## Sem Docker

1. Backend (em outro terminal, com o Ollama rodando e o modelo `bge-m3` baixado):

   ```bash
   cd SegundoChallenge/rag
   .venv/bin/pip install -r requirements.txt   # uma vez só
   .venv/bin/uvicorn api:app --reload --port 8000
   ```

2. Frontend:

   ```bash
   cd SegundoChallenge/Frontend
   npm install      # uma vez só
   npm run dev      # http://localhost:3000
   ```

Se a API estiver em outro endereço, defina `BACKEND_URL` (padrão: `http://127.0.0.1:8000`).

## Libras

O layout carrega o widget oficial do VLibras em todas as telas, após a hidratação.
O botão flutuante à direita abre o tradutor; o avatar é carregado sob demanda pelo
próprio serviço. Não inicializar manualmente `VLibras.Widget`: a versão atual já
inicializa automaticamente, evitando widgets duplicados.

Requer acesso à internet aos serviços do VLibras. Textos selecionados para tradução
são processados pelo serviço externo; não adicionar envio automático das mensagens
do chat. A tradução automática não equivale à validação humana em Libras.

Documentação: https://www.vlibras.gov.br/doc/widget/installation/webpageintegration.html

## Ferramentas de acessibilidade

O botão flutuante acima do VLibras abre um diálogo com ajuste de texto (100–150%),
alto contraste, destaque de links e redução de movimento. As preferências de
interface ficam no `localStorage` (`guia-social-accessibility`), sem conteúdo do
chat. Se o armazenamento estiver indisponível, os ajustes continuam em memória.
“Restaurar padrão” retorna a 100% e desliga os três ajustes. Escape fecha o painel
e devolve o foco ao botão de abertura. A preferência de movimento do sistema
continua sendo respeitada pelo CSS, independentemente do ajuste do painel.

O painel também oferece espaçamento de texto e uma seção de navegação por teclado.
O símbolo é um SVG decorativo com figura humana e círculo; o nome acessível está
no botão. O diálogo contém o foco ao percorrer Tab/Shift+Tab. Os rótulos, o foco
visível, o atalho “Ir para o conteúdo” e os controles nativos estão disponíveis
independentemente do painel. A redução de movimento se aplica também à rolagem
programática do chat. A revisão por teclado não substitui testes com NVDA/JAWS.

## RF02 — apresentação da resposta em linguagem simples

Os benefícios são apresentados em tópicos nas seções “O que é”, “Para quem é” e
“Quem pode pedir”. A divisão preserva a redação, ordem, valores e condições da
base; não usa truncamento nem cria critérios de elegibilidade. Termos detectados
podem ser consultados em “Entenda os termos”. A descrição, os critérios e a
legislação originais ficam em “Ver texto e referência da base”. A resposta integral
da API é preservada em “Ver resposta completa da base”, em vez de ser descartada.

Esta implementação cobre a apresentação no frontend. Extração de novos editais e
simplificação semântica de texto jurídico pela IA ainda dependem do backend.
A interface atual não afirma que apenas dividir frases equivale a essa geração.

## RNF02 — tamanhos e decisão de responsividade

Em 18/11/2026 o usuário decidiu manter o celular funcionando. A exigência histórica
de desktop exclusivo (1366×768) não foi aplicada. Fontes da aplicação têm mínimo
de 16 px em 100%; botões, campos e seletores/expansores nativos têm área mínima de
48×48 px. As fontes continuam respeitando o multiplicador de acessibilidade.
O VLibras é um serviço separado: o lançador tem 48×48 px, mas os controles internos
do player são gerenciados pelo fornecedor.

Testes de apresentação e preservação do texto:

```bash
node --experimental-strip-types --test lib/readable-text.test.mjs lib/benefit-card.test.mjs
```

## Entrada e saída de voz (frontend)

O início e a conversa têm botão de microfone. O frontend usa `SpeechRecognition`
(ou `webkitSpeechRecognition`) em pt-BR quando o navegador oferece o serviço.
A transcrição preenche o campo, permanece editável após parar e só é enviada à API
quando o usuário confirma o envio. Iniciar/parar também funciona pelo teclado no
botão. Há estados de espera de permissão, gravação, finalização e falha.
O serviço de reconhecimento pode processar a fala online; a aplicação não cria nem
persiste arquivos de áudio. A API atual continua recebendo apenas texto.

Respostas do assistente têm “Ouvir resposta”, pausar, continuar e parar com
`speechSynthesis`. A leitura é dividida em trechos para evitar corte de respostas
longas. Não há reprodução automática. Só uma resposta é lida por vez; nova
conversa, navegação e desmontagem encerram a leitura/captura da aplicação.
Iniciar gravação interrompe a leitura e iniciar leitura interrompe a gravação.

Quando o navegador não oferece uma das APIs, o controle fica indisponível e a
interface explica a alternativa por texto. Permissões reais, motores de voz e
qualidade/latência variam por navegador. Isto não comprova os requisitos de STT,
TTS neural e streaming no servidor (RIA03–RIA05), nem o limite de sessão RNF06.

Testes com motores simulados, sem captura real de microfone:

```bash
node --experimental-strip-types --test lib/speech-output.test.mjs
```

Referência: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
