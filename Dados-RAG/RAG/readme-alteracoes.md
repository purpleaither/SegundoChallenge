# Histórico técnico do RAG

## Arquitetura T5 aplicada

- O pipeline ativo foi alinhado ao relatório da Semana 3: embeddings `bge-m3` pelo Ollama, recuperação ChromaDB, limite por similaridade e resposta determinística montada com os campos revisados da base.
- Classificação e geração pela OpenAI foram removidas do caminho da API. O `bge-m3` não gera respostas; o modelo local de juiz RAGAS é opcional e usado somente na avaliação.
- O limiar configurável `RAG_MIN_SIMILARITY` usa inicialmente `0.532`, valor medido no corpus menor do relatório. O corpus atual contém mais trechos e precisa de recalibração independente antes de uso real.
- Os metadados indexados agora contêm campos para compor a resposta sem LLM; a versão do conjunto subiu para `programas-sociais-legislacao-v3`. Recrie o índice com `python .\Dados-RAG\RAG\ingestao.py`.
- Os dois endpoints de pergunta usam o mesmo `KnowledgeBase`; a busca lexical por interseção de palavras foi removida.
- Os imports e caminhos foram alinhados à estrutura atual `Dados-RAG/RAG` e ao CSV em `Dados-RAG/`.
- `executar_testes.py` roda os testes do back-end e do RAG por padrão. `--com-ragas` acrescenta a avaliação com RAGAS e juiz local Ollama; não há chamadas pagas no comando padrão nem na avaliação local.

## Testes e documentos

- `testes-automatizados/test_rag.py` verifica limiar de abstenção, filtro por versão, deduplicação, persistência e resposta determinística.
- `testes-automatizados/test_dataset.py` e `test_fontes.py` verificam validação do CSV e das fontes oficiais.
- `testes-automatizados/test_avaliar_ragas.py` valida os dados de avaliação e a configuração local.
- `Back-end/test_main.py` valida a API e seus limites de áudio sem depender de Ollama.
- Consulte [`README.md`](../../README.md) para instalação e comandos e [`Documentos/semana3-resumo.md`](../../Documentos/semana3-resumo.md) para a decisão e as limitações da Semana 3.

## Resultados históricos

Os JSONs `resultados/T1.json` a `T5.json` e `resultados/resumo.json` registram a comparação experimental do relatório. T1–T4 dependiam de modelos de resposta antigos e não representam a implementação atual. T5 foi escolhido, mas o resultado de 100% mede apenas as 27 perguntas daquele teste e não garante o mesmo desempenho no corpus atual.
