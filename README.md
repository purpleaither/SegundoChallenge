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
