# Geração AUmentada por Recuperação - RAG x LLM

Este diretório contém a base de recuperação de informações do assistente e os
scripts usados para preparar, consultar e avaliar essa base. O relatório da
comparação da Semana 3 está em
[`Documentos/Semana03-Relatorio-LLM-RAG.pdf`](../../Documentos/Semana03-Relatorio-LLM-RAG.pdf).

## Arquitetura atual

O fluxo atual não usa uma LLM generativa para redigir as respostas:

1. As perguntas são expandidas com termos relacionados.
2. O Ollama gera embeddings com o modelo `bge-m3`.
3. O ChromaDB recupera trechos da base de programas e de fontes oficiais.
4. Resultados abaixo do limiar de similaridade são descartados.
5. A resposta é montada a partir dos dados recuperados, com indicação das fontes.
   Sem contexto suficiente, o sistema se abstém de responder.

O limiar padrão é `0.532` e pode ser alterado pela variável
`RAG_MIN_SIMILARITY`. A base vetorial é derivada dos dados e pode ser recriada
com a ingestão.

## Preparar a base

Execute os comandos na raiz do repositório, em um PowerShell com o ambiente
Python do projeto ativado:

```powershell
ollama pull bge-m3
python .\Dados-RAG\RAG\baixar_fontes.py
python .\Dados-RAG\RAG\ingestao.py
```

`baixar_fontes.py` obtém os documentos legislativos das fontes oficiais. A
ingestão lê a base CSV, prepara os trechos, gera os embeddings, atualiza o
ChromaDB e grava fichas Markdown em `base/`.

## Avaliação

Para calcular métricas objetivas da recuperação:

```powershell
python .\Dados-RAG\RAG\avaliar.py
```

Para rodar os testes automatizados do back-end e do RAG:

```powershell
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py
```

Há também uma avaliação opcional com RAGAS e um juiz local. Consulte
[`testes-automatizados/COMO_EXECUTAR.md`](testes-automatizados/COMO_EXECUTAR.md)
para instalar as dependências extras e executar a avaliação.

O nome `experimentos.py` é mantido por compatibilidade e encaminha para a
avaliação RAGAS; ele não executa mais a comparação histórica T1–T5 da Semana 3.

## Arquivos principais

- `dataset.py`: Lê a base de programas e prepara os trechos e metadados.
- `fontes.py` e `baixar_fontes.py`: Obtêm e leem documentos oficiais.
- `ingestao.py`: Gera embeddings e atualiza o índice vetorial.
- `rag.py`: Implementa a busca, o limiar de similaridade e a resposta.
- `avaliar.py`: Mede a qualidade da recuperação.
- `avaliar_ragas.py`: Executa a avaliação RAGAS opcional.
- `testes-automatizados/`: Testes do RAG e instruções para executá-los.