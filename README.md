# Assistente virtual de benefícios sociais

API de perguntas e respostas sobre programas sociais. O sistema recupera informações da base curada e de fontes oficiais; as respostas são montadas a partir dos dados, sem geração por LLM. A resposta é informativa e não decide elegibilidade.

## Arquitetura adotada

O relatório [Documentos/semana3-resumo.md](Documentos/semana3-resumo.md) registra a decisão da Semana 03: usar a configuração T5 — embeddings multilíngues `bge-m3` pelo Ollama, busca vetorial ChromaDB, limiar de similaridade e resposta determinística. Isso elimina chamadas pagas e evita que um modelo reescreva ou invente leis e critérios.

O limiar padrão é `RAG_MIN_SIMILARITY=0.532`, valor experimental do relatório. Como a base atual também inclui textos legislativos, esse valor precisa ser recalibrado em um conjunto de perguntas independente antes de qualquer uso institucional.

## Estrutura real

- `Back-end/`: API FastAPI e testes do servidor.
- `Dados-RAG/programas_sociais_legislacao_links_oficiais.csv`: base estruturada dos 42 programas.
- `Dados-RAG/RAG/`: preparação dos dados, ingestão, recuperação, respostas determinísticas, avaliação RAGAS e testes.
- `Dados-RAG/RAG/base/`: fichas Markdown derivadas do CSV.
- `Dados-RAG/RAG/fontes/`: textos legislativos oficiais baixados.
- `Documentos/`: relatórios do projeto.

## Instalação e execução no Windows

Crie um ambiente com Python 3.12 e instale as dependências da API:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Back-end\requirements.txt
ollama pull bge-m3
```

Baixe fontes novas, se necessário, e gere/recrie o índice vetorial:

```powershell
python .\Dados-RAG\RAG\baixar_fontes.py
python .\Dados-RAG\RAG\ingestao.py
```

Inicie a API:

```powershell
python -m uvicorn main:app --reload --app-dir .\Back-end
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`. No Windows, o índice persistente fica por padrão em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3`; configure `VECTOR_DB_PATH` para outro local, se necessário. Depois da atualização para o conjunto v3, execute a ingestão novamente antes de consultar a API.

## Testes

Com as dependências instaladas, um comando executa os testes unitários do back-end e do RAG, sem Ollama, chave de API ou chamadas pagas:

```powershell
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py
```

O passo a passo está em [Dados-RAG/RAG/testes-automatizados/COMO_EXECUTAR.txt](Dados-RAG/RAG/testes-automatizados/COMO_EXECUTAR.txt).

### Avaliação RAGAS opcional

A avaliação RAGAS é separada da resposta da aplicação. Ela usa o endpoint OpenAI-compatível **local** do Ollama como juiz, sem `OPENAI_API_KEY` e sem custo de API:

```powershell
python -m pip install -r .\Dados-RAG\RAG\requirements-avaliacao.txt
ollama pull qwen2.5:3b
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas --limite 2
```

Para a bateria completa, remova `--limite 2`. O juiz local é outro modelo e suas notas também precisam de revisão; ele não participa da resposta ao cidadão.

RAGAS mede fidelidade da resposta e relação entre resposta, contextos e referências. Como o T5 não usa LLM para redigir, acompanhe também as métricas objetivas de recuperação e abstenção:

```powershell
python .\Dados-RAG\RAG\avaliar.py
```

Essa avaliação percorre as 27 perguntas e mede acerto@1, acerto@4, MRR e abstenção fora do escopo. Na revisão atual, o resultado foi **18/21 no top-1, 21/21 no top-4 e 6/6 abstenções**; há três casos em que o esperado não ficou em primeiro lugar. Como o limiar e as expansões foram ajustados com base nesses exemplos, isso não é um teste independente nem garantia de precisão. Além disso, algumas perguntas aceitam mais de um programa útil, então o conjunto precisa ser revisado para incluir alternativas válidas. As referências usadas por Context Precision/Recall também precisam de validação humana.

## Limitações conhecidas

- A base atual contém 42 programas federais, não um catálogo completo de benefícios do Distrito Federal.
- Os critérios da planilha são parciais em vários programas; a resposta preserva essa limitação.
- Similaridade vetorial é apenas uma estimativa de relevância, não uma classificação semântica infalível de escopo. Perguntas ambíguas ou fora da base podem exigir revisão e recalibração do limiar.
- O corpus e o conjunto de avaliação são pequenos para certificar precisão ou elegibilidade.
