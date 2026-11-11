# Histórico de alterações do RAG e da interface

Este documento resume o que foi alterado, o que está ativo e o que permanece fora do escopo atual. As linhas abaixo são **referências aos trechos atuais dos arquivos**, não números de um diff: o workspace não disponibiliza um histórico Git para comparar cada versão anterior.

## RAG e base vetorial

| Arquivo e linhas atuais | Alteração / responsabilidade |
|---|---|
| [`dataset.py`](dataset.py), linhas 18–112 | Define o CSV como fonte e valida codificação, colunas, registros e URLs oficiais antes de usar os dados. |
| [`dataset.py`](dataset.py), linhas 114–176 | Converte as colunas disponíveis em registros da API e documentos Markdown, sem preencher critérios ausentes com suposições. |
| [`dataset.py`](dataset.py), linhas 179–213 | Cria quatro seções contextualizadas por programa e seus metadados para recuperação e citação. |
| [`fontes.py`](fontes.py) e [`baixar_fontes.py`](baixar_fontes.py) | Baixam HTML de domínios oficiais, extraem texto legislativo reconhecível e salvam metadados e conteúdo em `fontes/`; falhas e PDFs não suportados são informados. |
| [`dataset.py`](dataset.py) | Exige pelo menos 20 URLs oficiais distintas com texto integral antes de criar trechos legislativos. |
| [`rag.py`](rag.py), linhas 16–51 | Configura o caminho do ChromaDB (no Windows, `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2` por padrão), os modelos Ollama, a versão do corpus e as expansões de consulta. |
| [`rag.py`](rag.py), linhas 86–111 | Implementa a divisão de texto em trechos, com limite de tamanho e sobreposição. |
| [`rag.py`](rag.py), linhas 151–218 | Monta o contexto com programa, órgão e status dos critérios; orienta a geração e substitui respostas sem citações válidas por uma resposta baseada no trecho recuperado. |
| [`rag.py`](rag.py), linhas 220–294 | Persiste e substitui vetores no ChromaDB; consulta a versão atual, limita a distância e deduplica resultados por programa. |
| [`ingestao.py`](ingestao.py), linhas 24–62 | Gera documentos derivados em `Dados/rag/base`, cria embeddings pelo `bge-m3` e grava os vetores persistentes. |
| [`buscar.py`](buscar.py), linhas 1–47 | Demonstra a recuperação e exibe programa, fonte, similaridade e trecho. |
| [`avaliar.py`](avaliar.py), linhas 1–53 | Executa perguntas representativas e calcula acerto@5 da recuperação. Isso não avalia a veracidade da resposta gerada. |
| [`test_rag.py`](testes-automatizados/test_rag.py) | Testa expansão, deduplicação, filtro de vetores antigos, citações e fallback para respostas sem citações válidas. |
| [`test_dataset.py`](testes-automatizados/test_dataset.py) | Testa leitura e validação do CSV, lacunas, criação dos trechos e documentos derivados. |
| [`Back-end/main.py`](../../Back-end/main.py), linhas 18–20 e 407–472 | Importa o RAG de `Dados/rag` e usa recuperação, geração e fontes citadas na rota de chat. |

### Estado do índice

O índice antigo em `Dados/vetor/` estava incompleto: faltavam os arquivos HNSW de dados. A ingestão em uma pasta do projeto cujo caminho contém acentos também não persistiu os arquivos HNSW; por isso, no Windows, o padrão passou para `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`. Nesta revisão, o coletor baixou **27 textos legislativos integrais** de URLs oficiais distintas, que geram 1.036 trechos, somados a 168 trechos estruturados: **1.204 vetores**. A persistência dos arquivos HNSW e a reabertura em processo novo foram verificadas nesse caminho. Dois links da Imprensa Nacional são PDFs ainda não suportados e uma página legislativa retornou erro temporário.

```powershell
python .\Dados\rag\baixar_fontes.py
python .\Dados\rag\ingestao.py
```

O CSV continua sendo a fonte dos dados estruturados; os textos em `Dados/rag/fontes/` preservam as fontes integrais baixadas; o índice local é derivado dessas duas fontes. O indexador usa `bge-m3`; a geração de respostas usa `qwen2.5:3b`.

## Interface do chat

| Arquivo e linhas atuais | Alteração / responsabilidade |
|---|---|
| [`Front-end/index.html`](../../Front-end/index.html), linhas 12–29 | Adiciona o menu hambúrguer no cabeçalho com atalhos para programas, órgãos, avisos e acesso à conta. |
| [`Front-end/index.html`](../../Front-end/index.html), linhas 33–68 | Enxuga o título e mantém a conversa e a caixa de pergunta como conteúdo principal. |
| [`Front-end/index.html`](../../Front-end/index.html), linhas 70–105 | Recolhe inicialmente a lista de programas, os órgãos responsáveis e as informações importantes. |
| [`Front-end/app.js`](../../Front-end/app.js), linhas 78–124 | Recolhe as fontes de cada resposta em um painel expansível, reduzindo conteúdo visual repetido no chat. |
| [`Front-end/app.js`](../../Front-end/app.js), linhas 397–417 | Fecha o menu ao selecionar uma seção, expande o destino e dá suporte à tecla Escape. |
| [`Front-end/style.css`](../../Front-end/style.css), linhas 71–131 | Estiliza o menu e seus itens de navegação. |
| [`Front-end/style.css`](../../Front-end/style.css), linhas 136–190 e 305–338 | Reduz espaçamentos do chat e limita a altura da conversa. |
| [`Front-end/style.css`](../../Front-end/style.css), linhas 339–372 | Estiliza as citações recolhíveis em cada resposta. |
| [`Front-end/style.css`](../../Front-end/style.css), linhas 384–435 e 491–501 | Estiliza seções recolhíveis, seus indicadores e o painel de informações importantes. |
| [`Front-end/style.css`](../../Front-end/style.css), linhas 591–646 | Adapta o cabeçalho, o chat e as seções recolhíveis para telas estreitas. |

## Autenticação: somente protótipo visual

[`Front-end/conta.html`](../../Front-end/conta.html), linhas 20–100, apresenta abas e campos para login, cadastro e recuperação de senha. Os controles estão desativados e avisam que não há serviço conectado. [`Front-end/conta.js`](../../Front-end/conta.js), linhas 1–26, somente controla a navegação acessível entre as abas.

**Não foram implementados** autenticação, cadastro persistente, validação de senha no servidor, banco relacional de contas, criação/verificação de token ou envio de e-mail. A tela não deve ser tratada como login funcional nem usada com credenciais reais. Essas partes dependem da futura API, do banco e da configuração do serviço de e-mail.

## O que não foi alterado ou ainda está pendente

- O CSV e os dados-fonte não foram alterados nesta reorganização da interface.
- A base tem 27 textos legislativos integrais coletados e indexados de páginas oficiais. Dois links em PDF não são extraídos e uma página retornou erro temporário.
- A cobertura e a revisão humana das regras de elegibilidade continuam parciais; os textos legais não substituem regras operacionais atualizadas nem um catálogo completo do DF.
- A base atual cobre programas federais; não é um catálogo completo de benefícios do Distrito Federal.
- O acerto@5 mede a posição do programa esperado nos resultados recuperados, não a precisão factual de cada resposta do modelo.
- O chat continua disponível sem autenticação; as telas de conta são apenas um protótipo desativado.

## Verificações executadas na revisão anterior

- Testes do back-end: **11 passaram**.
- Testes do RAG: **20 passaram**.
- Os modelos `bge-m3` e `qwen2.5:3b` foram usados com sucesso. A busca real retornou trechos legislativos; a avaliação de recuperação foi **11/11 (100%)**; e `POST /api/chat` respondeu HTTP 200 com resposta e citações. A avaliação não comprova a veracidade factual das respostas.
- `node --check` passou para `Front-end/app.js` e `Front-end/conta.js`.
- A tela inicial e as abas do protótipo de conta foram abertas no navegador. A API não estava em execução durante a verificação visual, então os dados dinâmicos do chat não foram testados nessa sessão.

## Unificação da avaliação RAG + RAGAS e verificação de escopo (2026-11-10)

| Arquivo | Alteração |
|---|---|
| [`rag.py`](rag.py) | Adiciona classificação semântica da intenção com Ollama antes de gerar uma resposta. A classificação considera o sentido da pergunta e o histórico recente; não usa os documentos recuperados nem uma palavra-chave isolada para afirmar relevância. Perguntas fora do escopo recebem abstenção fixa; perguntas pertinentes sem contexto recebem aviso de ausência de evidência. |
| [`Back-end/main.py`](../../Back-end/main.py) | Encaminha também perguntas sem trechos ao fluxo comum de resposta e não anexa citações de busca após uma abstenção de escopo. |
| [`buscar.py`](buscar.py) | Adiciona `--responder` e `--modelo` para experimentar a recuperação e a geração do modelo em uma pergunta pelo terminal. |
| [`avaliar_ragas.py`](avaliar_ragas.py), [`avaliacao/casos.jsonl`](avaliacao/casos.jsonl) e [`requirements-avaliacao.txt`](requirements-avaliacao.txt) | Integra casos e dependências RAGAS ao diretório único do RAG. O avaliador executa a busca e geração reais da aplicação, computa métricas de aderência ao escopo para todas as perguntas e métricas de evidência para as perguntas em escopo. A bateria amplia os casos negativos com perguntas contendo palavras sociais como distração. |
| [`README.md`](../../README.md), [`README.md`](README.md) e [`terminal.txt`](../../terminal.txt) | Atualizam a organização: `Dados/rag-ragas/` fica preservado como arquivo histórico e os comandos ativos passam a usar `Dados/rag/`. |

A referência anterior registrava abstenção em **1/4** perguntas fora do escopo. A nova implementação passa a verificar a intenção antes da geração e a bateria automatizada mede novamente esse comportamento contra os casos, sem presumir que a correção está validada até executar o Ollama com o índice local.

**Validação desta alteração:** 13 testes do back-end e 13 testes de dados/fontes passaram; a checagem de sintaxe, o CLI do avaliador e testes isolados do caminho de classificação também passaram. A suíte que importa ChromaDB e o RAGAS completo não foram executados: o único Python disponível neste ambiente é 3.15.2, para o qual a instalação falhou por falta de wheel do `onnxruntime`; além disso, o servidor Ollama não tem modelos baixados. O resultado de 1/4 acima pertence ao experimento histórico, não ao novo fluxo.
