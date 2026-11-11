# Abstenção e respostas fundamentadas — v3

Classificador local: `qwen2.5:3b`. Busca híbrida BM25 + vetorial, com expansão de vocabulário. Respostas extraídas das fichas, sem geração livre de critérios. Mesmos 25 casos da bateria histórica.

| Indicador | v2 | v3 |
|---|---:|---:|
| Perguntas dentro do escopo respondidas | 0/21 | 21/21 |
| Abstenções dentro do escopo | 21/21 | 0/21 |
| Abstenções fora do escopo | 4/4 | 4/4 |
| Programa esperado no top-4 | — | 21/21 |
| Programa esperado presente na resposta | — | 21/21 |

## Interpretação

O juiz de pertinência foi removido: confundia informação parcial com impossibilidade de orientar. A busca híbrida inclui fichas que ficavam fora dos candidatos vetoriais, como FIES e distribuição de alimentos. A resposta extrativa preserva público, critérios, situação do critério, legislação, observações e fonte. Não afirma elegibilidade individual.

A seleção usa um corte relativo de 75% do maior score lexical. Os pesos, a expansão e esse corte foram ajustados nesta bateria; o resultado não demonstra generalização. Presença do programa esperado e fidelidade aos campos não comprovam atualidade normativa nem correção da base. Perguntas amplas podem incluir programas adicionais; os respectivos públicos e critérios permanecem explícitos. As métricas RAGAS não foram recalculadas.

## Verificações adicionais

Três paráfrases sobre energia, financiamento estudantil e cesta de alimentos receberam orientação com os programas esperados. Receita culinária e filme foram recusados; consulta de CPF/cadastro também. O benefício fictício Zorblax gerou abstenção, mas o classificador o marcou como fora do escopo: o motivo mais adequado seria falta de evidências. Essa limitação permanece registrada.

## Resultados por caso

| Caso | Pergunta | Decisão | Programa esperado na resposta |
|---|---|---|---|
| dentro-1 | Estou desempregada e tenho três filhos, tenho direito a algum auxílio? | respondida | Sim |
| dentro-2 | tem ajuda para comprar o botijão de gás? | respondida | Sim |
| dentro-3 | minha conta de luz tá muito cara, tem desconto? | respondida | Sim |
| dentro-4 | tem desconto na conta de água? | respondida | Sim |
| dentro-5 | minha mãe é idosa e não tem renda nenhuma | respondida | Sim |
| dentro-6 | meu filho é deficiente, tem algum benefício? | respondida | Sim |
| dentro-7 | quero fazer faculdade mas não tenho dinheiro | respondida | Sim |
| dentro-8 | como faço pra não pagar a inscrição do enem? | respondida | Sim |
| dentro-9 | tem isenção pra taxa de concurso? | respondida | Sim |
| dentro-10 | meu filho tá no ensino médio, tem alguma ajuda? | respondida | Sim |
| dentro-11 | quero comprar uma casa, tem programa do governo? | respondida | Sim |
| dentro-12 | preciso de remédio de graça | respondida | Sim |
| dentro-13 | onde consigo absorvente de graça? | respondida | Sim |
| dentro-14 | moro na roça e falta água por causa da seca | respondida | Sim |
| dentro-15 | sou dona de casa, posso pagar o INSS mais barato? | respondida | Sim |
| dentro-16 | deficiente pode viajar de ônibus de graça pra outro estado? | respondida | Sim |
| dentro-17 | quero abrir um negócio pequeno, tem microcrédito? | respondida | Sim |
| dentro-18 | preciso de internet pro meu filho estudar | respondida | Sim |
| dentro-19 | tem cesta de comida pra família passando fome? | respondida | Sim |
| dentro-20 | estou grávida, tem acompanhamento pro bebê? | respondida | Sim |
| dentro-21 | quais benefícios posso ter como mãe solteira de baixa renda? | respondida | Sim |
| fora-1 | qual o melhor time de futebol do brasil? | fora_do_escopo | — |
| fora-2 | como faço bolo de cenoura? | fora_do_escopo | — |
| fora-3 | qual a previsão do tempo pra amanhã? | fora_do_escopo | — |
| fora-4 | me recomenda um filme de terror | fora_do_escopo | — |

## Artefatos

- [Coleta final](amostras_abstencao_v3_validada.jsonl)
- [Resumo](resumo_abstencao_v3.json)
- [Casos adicionais](casos_abstencao_v3_extras.jsonl)
- [Respostas adicionais](amostras_abstencao_v3_extras.jsonl)
