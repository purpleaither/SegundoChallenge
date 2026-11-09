# Avaliação RAGAS — bateria completa

Execução local com `qwen2.5:3b` como gerador e juiz. Foram coletadas 25 respostas: 21 dentro do escopo e quatro fora. As referências foram redigidas a partir da base local, com arquivo de origem e SHA-256 registrados em `casos.jsonl`; não passaram por validação externa ou revisão humana independente.

## Métricas RAGAS

As médias abaixo incluem apenas os 21 casos dentro do escopo. Valores maiores indicam melhor desempenho segundo o juiz, mas as notas são exploratórias e precisam de revisão.

| Métrica | Média | Avaliadas | Falhas técnicas |
|---|---:|---:|---:|
| Faithfulness | 0.543 | 21 | 0 |
| Context Utilization | 0.595 | 21 | 0 |
| Context Precision | 0.421 | 21 | 0 |
| Context Recall | 0.888 | 21 | 0 |

## Achados

- Recuperação do programa esperado (`acerto_top_k`, indicador próprio): **19/21 (90,5%)**. FIES Social não apareceu para a pergunta sobre faculdade; ADA não apareceu para a pergunta sobre cesta de alimentos.
- Abstenção (`abstencao_heuristica`, indicador próprio): **1/4 (25%)**. A inspeção das respostas confirma recusa para futebol, mas respostas sobre benefícios para bolo de cenoura, previsão do tempo e filmes.
- No caso da cesta de alimentos, Context Precision e Context Recall foram 0,0, coerentes com a ausência do programa esperado.
- No caso do FIES Social, Context Recall foi 1,0 mesmo sem recuperar esse programa. O contexto continha Sisu e PNAES, que podem ser pertinentes à pergunta ampla, mas a referência descreve financiamento pelo FIES. Esse julgamento precisa de revisão.
- Há notas de Faithfulness baixas para respostas que reproduzem informações das fichas. Isso pode refletir tanto problemas nas respostas quanto erros do juiz; as médias não demonstram correção factual ou atualidade normativa.
- Gerador e juiz usam o mesmo modelo pequeno; uma avaliação posterior deve comparar uma amostra revisada por humanos e, se disponível, um juiz mais capaz.

## Execução e recuperação de falhas

A primeira passagem teve quatro saídas truncadas em Faithfulness. A retomada com `--max-tokens 4096` repetiu apenas essas chamadas e preservou as demais notas. O resultado final tem 84 notas válidas e nenhuma falha técnica. O campo `max_tokens_por_metrica` registra o limite nas quatro chamadas repetidas; as notas da primeira passagem não tinham esse metadado.

## Resultados por pergunta

| Caso | Pergunta | Faithfulness | Context Utilization | Context Precision | Context Recall | Acerto top-k |
|---|---|---:|---:|---:|---:|---|
| dentro-1 | Estou desempregada e tenho três filhos, tenho direito a algum auxílio? | 0.300 | 1.000 | 0.000 | 0.857 | Sim |
| dentro-2 | tem ajuda para comprar o botijão de gás? | 0.417 | 1.000 | 0.750 | 1.000 | Sim |
| dentro-3 | minha conta de luz tá muito cara, tem desconto? | 0.900 | 0.000 | 0.000 | 0.800 | Sim |
| dentro-4 | tem desconto na conta de água? | 0.875 | 1.000 | 1.000 | 1.000 | Sim |
| dentro-5 | minha mãe é idosa e não tem renda nenhuma | 0.000 | 0.750 | 0.750 | 0.750 | Sim |
| dentro-6 | meu filho é deficiente, tem algum benefício? | 0.167 | 1.000 | 0.750 | 1.000 | Sim |
| dentro-7 | quero fazer faculdade mas não tenho dinheiro | 0.000 | 1.000 | 0.000 | 1.000 | Não |
| dentro-8 | como faço pra não pagar a inscrição do enem? | 0.000 | 0.000 | 1.000 | 0.750 | Sim |
| dentro-9 | tem isenção pra taxa de concurso? | 0.417 | 0.000 | 1.000 | 1.000 | Sim |
| dentro-10 | meu filho tá no ensino médio, tem alguma ajuda? | 1.000 | 0.000 | 0.000 | 1.000 | Sim |
| dentro-11 | quero comprar uma casa, tem programa do governo? | 1.000 | 0.750 | 0.750 | 1.000 | Sim |
| dentro-12 | preciso de remédio de graça | 0.300 | 0.000 | 0.000 | 0.600 | Sim |
| dentro-13 | onde consigo absorvente de graça? | 1.000 | 1.000 | 0.000 | 1.000 | Sim |
| dentro-14 | moro na roça e falta água por causa da seca | 0.600 | 1.000 | 0.000 | 1.000 | Sim |
| dentro-15 | sou dona de casa, posso pagar o INSS mais barato? | 0.818 | 0.000 | 0.000 | 1.000 | Sim |
| dentro-16 | deficiente pode viajar de ônibus de graça pra outro estado? | 1.000 | 0.000 | 0.500 | 1.000 | Sim |
| dentro-17 | quero abrir um negócio pequeno, tem microcrédito? | 0.000 | 1.000 | 1.000 | 1.000 | Sim |
| dentro-18 | preciso de internet pro meu filho estudar | 1.000 | 1.000 | 1.000 | 1.000 | Sim |
| dentro-19 | tem cesta de comida pra família passando fome? | 0.833 | 0.000 | 0.000 | 0.000 | Não |
| dentro-20 | estou grávida, tem acompanhamento pro bebê? | 0.000 | 1.000 | 0.000 | 0.889 | Sim |
| dentro-21 | quais benefícios posso ter como mãe solteira de baixa renda? | 0.778 | 1.000 | 0.333 | 1.000 | Sim |

## Arquivos

- `../casos.jsonl`: perguntas e referências com origem e hash.
- `../amostras_completas.jsonl`: respostas, contextos e referências usados nesta execução.
- `resultados.jsonl`: notas e metadados por pergunta.
- `metricas.csv`: tabela de métricas.
- `resumo.json`: médias e contagens.

## Próximos ajustes

1. Revisar manualmente as referências e as discrepâncias do juiz antes de definir metas de qualidade.
2. Corrigir a abstenção fora do escopo, que falhou em três das quatro perguntas testadas.
3. Investigar a recuperação para FIES Social e ADA e ampliar os testes com perguntas que aceitam vários programas.
4. Reavaliar as mesmas respostas com um juiz mais capaz, em outra pasta de saída, para comparar as notas.
