# Alterações feita no RAG

Este documento resume o que foi alterado, o que está ativo e o que permanece fora do escopo atual.<br>

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
| [`test_rag.py`](test_rag.py), linhas 42–169 | Testa expansão, deduplicação, filtro de vetores antigos, citações e fallback para respostas sem citações válidas. |
| [`test_dataset.py`](test_dataset.py), linhas 20–134 | Testa leitura e validação do CSV, lacunas, criação dos trechos e documentos derivados. |
| [`Back-end/main.py`](../../Back-end/main.py), linhas 18–20 e 407–472 | Importa o RAG de `Dados/rag` e usa recuperação, geração e fontes citadas na rota de chat. |

### Estado do índice

O índice antigo em `Dados/vetor/` estava incompleto: faltavam os arquivos HNSW de dados. A ingestão em uma pasta do projeto cujo caminho contém acentos também não persistiu os arquivos HNSW; por isso, no Windows, o padrão passou para `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`. Nesta revisão, o coletor baixou **27 textos legislativos integrais** de URLs oficiais distintas, que geram 1.036 trechos, somados a 168 trechos estruturados: **1.204 vetores**. A persistência dos arquivos HNSW e a reabertura em processo novo foram verificadas nesse caminho. Dois links da Imprensa Nacional são PDFs ainda não suportados e uma página legislativa retornou erro temporário.

```powershell
python .\Dados\rag\baixar_fontes.py
python .\Dados\rag\ingestao.py
```

O CSV continua sendo a fonte dos dados estruturados; os textos em `Dados/rag/fontes/` preservam as fontes integrais baixadas; o índice local é derivado dessas duas fontes. O indexador usa `bge-m3`; a geração de respostas usa `qwen2.5:3b`.

## O que não foi alterado ou ainda está pendente

- O CSV e os dados-fonte não foram alterados nesta reorganização da interface.
- A base tem 27 textos legislativos integrais coletados e indexados de páginas oficiais. Dois links em PDF não são extraídos e uma página retornou erro temporário.
- A cobertura e a revisão humana das regras de elegibilidade continuam parciais; os textos legais não substituem regras operacionais atualizadas nem um catálogo completo do DF.
- A base atual cobre programas federais; não é um catálogo completo de benefícios do Distrito Federal.
- O acerto@5 mede a posição do programa esperado nos resultados recuperados, não a precisão factual de cada resposta do modelo.
- O chat continua disponível sem autenticação; as telas de conta são apenas um protótipo desativado.

## Verificações executadas

- Testes do back-end: **11 passaram**.
- Testes do RAG: **20 passaram**.
- Os modelos `bge-m3` e `qwen2.5:3b` foram usados com sucesso. A busca real retornou trechos legislativos; a avaliação de recuperação foi **11/11 (100%)**; e `POST /api/chat` respondeu HTTP 200 com resposta e citações. A avaliação não comprova a veracidade factual das respostas.
