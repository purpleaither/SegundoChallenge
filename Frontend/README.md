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
