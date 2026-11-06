# RAG do Assistente do DF

Este diretório contém a implementação única do RAG: leitura e validação da base, preparação de documentos, busca vetorial, geração de respostas e comandos de ingestão e avaliação. A API importa os módulos daqui.

## Arquitetura atual

1. **Fonte de conhecimento:** `../programas_sociais_legislacao_links_oficiais.csv`, com 42 programas federais e 22 colunas, fornece os dados estruturados. Os arquivos Markdown em `base/` são documentos derivados dos registros, não fontes independentes. O coletor `baixar_fontes.py` baixa textos legislativos integrais de URLs oficiais distintas e grava as fontes em `fontes/`; nesta coleta, 27 páginas HTML foram validadas e indexadas.
2. **Tratamento e chunking:** o pipeline valida esquema, campos essenciais e URLs oficiais; transforma cada programa em quatro seções semânticas e cria 168 trechos estruturados. Também divide os textos legislativos baixados em trechos de até 1.200 caracteres, com sobreposição de 180 caracteres e ajuste por espaço. Cada trecho é contextualizado com o programa e a fonte.
3. **Embeddings:** Ollama executa `bge-m3` para converter os trechos e as perguntas (após expansão de alguns termos) em vetores. A ingestão envia os trechos em lotes de até 32; a busca usa o mesmo modelo de embedding.
4. **Banco vetorial:** ChromaDB persiste esses vetores usando distância cosseno. No Windows, o local padrão é `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`; em outros sistemas, é `Dados/vetor-v2/`. `VECTOR_DB_PATH` permite configurar outro local. O índice é derivado e pode ser recriado a partir do CSV e das fontes baixadas.
5. **Recuperação e geração:** o RAG expande alguns termos populares, busca trechos, limita distância, filtra a versão atual e deduplica por programa. Ollama executa `qwen2.5:3b` para redigir uma resposta com as fontes recuperadas.
6. **Aplicação:** a API entrega a resposta e as referências ao front-end.

O mapeamento dos requisitos do segundo desafio, o estado das evidências e os passos para a demonstração estão em [`semana_2.md`](../../Documentacao/semana_2.md).

```mermaid
flowchart LR
    CSV["CSV curado<br/>42 programas"] --> Validate["Validar esquema,<br/>campos e URLs"]
    Validate --> Docs["Documentos derivados<br/>4 seções por programa"]
    CSV --> Fetch["Baixar URLs legislativas oficiais"]
    Fetch --> Laws["Textos integrais validados<br/>fontes/"]
    Docs --> Chunks["Chunking contextual"]
    Laws --> Chunks
    Chunks --> Embed["Ollama<br/>bge-m3"]
    Embed --> Store[("ChromaDB<br/>AppData Local/AssistenteVirtualDF/vetor-v2")]
    Question["Pergunta"] --> Expand["Expansões de termos"]
    Expand --> QueryEmbed["Ollama<br/>bge-m3"]
    QueryEmbed --> Search["Busca vetorial<br/>versão + distância"]
    Store --> Search
    Search --> Dedupe["Deduplicar por programa"]
    Dedupe --> Answer["Ollama<br/>qwen2.5:3b"]
    Answer --> API["API"]
    API --> UI["Front-end"]
```

## O que já foi feito no RAG

- Centralização do código de RAG em `Dados/rag/`; não há uma segunda implementação usada pelo back-end.
- Validação do CSV e preservação explícita de critérios e público-alvo ausentes ou parciais.
- Coleta de textos legislativos integrais apenas de domínios oficiais, com validação do conteúdo e aviso explícito para links indisponíveis ou formatos não suportados.
- Divisão por seções semânticas, com o programa e a seção no contexto de cada trecho.
- Persistência de embeddings no ChromaDB no caminho local padrão do sistema.
- Expansão de consultas para alguns termos cotidianos, filtro por versão do conjunto, limite de distância e deduplicação por programa.
- Respostas orientadas a usar somente os trechos encontrados, citar as fontes, explicitar lacunas e não decidir elegibilidade.
- Contexto de geração melhorado com nome do programa, órgão responsável e status dos critérios em campos separados; o prompt agora proíbe deduzir o órgão pelo tema, título da fonte ou URL. A temperatura está em zero para reduzir variação, sem garantir ausência total de alucinações.
- Testes automatizados de parsing, indexação, recuperação, filtros, citações e integração da API.

## O que ainda não foi feito

- **Curadoria da base:** 27 textos legislativos integrais foram coletados de páginas oficiais e indexados. Dois links da Imprensa Nacional são PDFs e ainda não são extraídos; uma página legislativa retornou erro temporário. A coleta atinge o mínimo de 20 documentos, mas as informações de elegibilidade da planilha permanecem parciais e precisam de revisão humana.
- **Cobertura completa do DF:** os 42 registros são programas federais; o catálogo distrital não está completo.
- **Autenticação:** há apenas telas de protótipo em `Front-end/conta.html`. Login, cadastro, recuperação de senha, envio de token e gerenciamento de contas estão desativados; não há API de autenticação, banco de contas nem serviço de e-mail.
- **Garantia de veracidade das respostas:** o modelo pode errar mesmo com recuperação correta. O protótipo precisa de testes de resposta com perguntas reais e revisão humana antes de uso institucional.

## Instalação e execução

Instale as dependências do back-end e mantenha o Ollama em execução com os dois modelos:

```powershell
python -m pip install -r .\Back-end\requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:3b
```

Baixe/atualize os textos legislativos e gere os vetores depois de modificar o CSV ou as fontes:

```powershell
python .\Dados\rag\baixar_fontes.py
python .\Dados\rag\ingestao.py
```

Consulte trechos ou avalie a recuperação@5:

```powershell
python .\Dados\rag\buscar.py "Tem ajuda para comprar o botijão de gás?"
python .\Dados\rag\avaliar.py
```

`avaliar.py` mede se o programa esperado aparece nos primeiros cinco resultados; não mede a precisão factual das respostas geradas. Nesta revisão, o resultado foi **11/11 (100%)** para os casos de teste definidos. No Windows, o banco persistente fica em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`; a recuperação requer `bge-m3` e a geração requer `qwen2.5:3b`. Use um caminho sem acentos ao configurar `VECTOR_DB_PATH` no Windows.
