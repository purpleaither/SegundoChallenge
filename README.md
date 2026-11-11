# Bot Auxílios Para Pessoas de Baixa Renda

Assistente de orientação sobre programas sociais federais, com recuperação em ChromaDB, geração local no Ollama e avaliação com RAGAS.

## Resultados da avaliação RAGAS

Bateria de 25 perguntas com `qwen2.5:3b` como gerador e juiz. As métricas RAGAS abaixo cobrem os 21 casos dentro do escopo.

| Métrica RAGAS | Média | Casos avaliados |
|---|---:|---:|
| Faithfulness | 0.543 | 21 |
| Context Utilization | 0.595 | 21 |
| Context Precision | 0.421 | 21 |
| Context Recall | 0.888 | 21 |

| Indicador próprio do projeto | Resultado | Taxa |
|---|---:|---:|
| Programa esperado recuperado no top-4 | 19/21 | 90,5% |
| Abstenção em perguntas fora do escopo | 1/4 | 25,0% |

As referências vêm da base local e ainda precisam de revisão humana. As notas são exploratórias; o relatório registra discrepâncias do juiz e falhas de abstenção.

- [Como executar o RAG e a avaliação](rag/README.md)
- [Relatório completo e tabelas por pergunta](rag/avaliacao/resultados_completos/relatorio.md)
- [Tabela de métricas em CSV](rag/avaliacao/resultados_completos/metricas.csv)

## Resultados da abstenção — v2

Nova coleta no Ollama com `qwen2.5:3b`, usando as mesmas 25 perguntas da bateria
histórica, após adicionar classificação de escopo e validação das evidências.

| Indicador próprio do projeto | Resultado v2 | Taxa |
|---|---:|---:|
| Abstenção em perguntas fora do escopo | 4/4 | 100,0% |
| Não respostas em perguntas dentro do escopo | 21/21 | 100,0% |

A abstenção fora do escopo passou de 1/4 para 4/4, mas o sistema também deixou de
responder a todas as 21 perguntas válidas. Foram 20 decisões `sem_evidencia` e
uma classificação incorreta como `fora_do_escopo` entre essas perguntas.
**A v2 apresentou regressão por excesso de abstenção e ainda precisa de ajuste.**
Os nove testes de fluxo passaram, mas não comprovam a qualidade das decisões do modelo.

Estas contagens são indicadores do pipeline. As métricas RAGAS não foram
recalculadas para a v2; as notas da bateria histórica acima permanecem separadas.

- [Relatório v2 com os motivos por pergunta](rag/avaliacao/relatorio_abstencao_v2.md)
- [Resumo v2 em JSON](rag/avaliacao/resumo_abstencao_v2.json)
- [Respostas e decisões da v2](rag/avaliacao/amostras_abstencao_v2.jsonl)
