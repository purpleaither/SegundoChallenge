> Atualização: a rota ativa agora é `/api/orientar`, integrada ao módulo
> `sistema_multiagente`. Há Markdown, apoio separado e texto preparado para Piper.
> [Configuração e limites atuais](../Back-end/INTEGRACAO.md).
> Referências a `/api/assistant` e T5 abaixo registram etapas anteriores.

# GuIA Social — frontend

A interface usa a API atual do GitHub em `Back-end/main.py`, rota `/api/assistant`.
Consulte [como iniciar a integração](../Back-end/INTEGRACAO.md).
A resposta completa fica visível; fontes e detalhes dos programas ficam logo abaixo.
O endpoint histórico `/api/perguntar` e as descrições históricas abaixo sobre `rag/`
não representam mais o caminho ativo das perguntas.

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

O início e a conversa têm botão de microfone. A captura usa AudioWorklet e a
transcrição progressiva ocorre no serviço local Whisper via `/api/stt` (porta 8002).
Prévias aparecem durante a fala com o modelo small, sem duplicar o rascunho.
Ao parar, o microfone é liberado e large-v3-turbo revisa a transcrição final.
O usuário revisa o texto antes de enviar. Há limite de 60 segundos e 8 MiB,
tratamento de permissão, silêncio, falha de rede e cancelamento na navegação.
Veja [instalação e limites do STT](../rag/STT.md). HTTPS ou localhost é necessário.

Respostas do assistente usam o serviço local Piper em pt-BR por `/api/tts`.
Há controles de ouvir, pausar, continuar, parar e repetir. A leitura ocorre em
trechos, com antecipação do próximo áudio e cache em memória para replay.
Não há reprodução automática. Nova conversa e navegação encerram a leitura e
limpam o cache. Iniciar gravação interrompe a leitura e vice-versa.

Veja [configuração e limites do TTS](../rag/TTS.md). O serviço deve estar iniciado
na porta 8001, ou configurado via `TTS_URL`. Falhas são apresentadas junto ao player.
A gravação depende do suporte a AudioWorklet e da permissão de microfone. Os testes automatizados não
comprovam MOS, latência sob carga, captura real do microfone ou o limite RNF06.

Testes com motores simulados, sem captura real de microfone:

```bash
node --experimental-strip-types --test lib/*.test.mjs
```

Referência: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API

### Leitura automática opcional

A conversa oferece “Ler novas respostas automaticamente”, desativada por padrão.
A escolha é salva no navegador. Somente respostas recebidas com a opção ativa,
conversa aberta e microfone inativo iniciam a leitura; sugestões, mensagem inicial,
erros e histórico não iniciam áudio automaticamente. Desativar interrompe a leitura.
Os controles de pausa, parada e replay continuam disponíveis. O navegador pode
bloquear reprodução automática; nesse caso o player informa a falha e permite
iniciar a leitura pelo botão.
