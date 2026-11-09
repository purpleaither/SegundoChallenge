# Relatório Comparativo: LLM Pura vs. LLM com RAG (Semana 3 — Grupo 7)

- **Modelo utilizado:** `qwen2.5:3b` (rodando localmente via Ollama com `temperature = 0.0`)
- **Total de perguntas testadas:** 12 (9 dúvidas reais sobre benefícios + 3 perguntas fora do escopo)

---

## 1. Resumo dos Resultados

| O que foi avaliado | LLM Pura (Sem a base) | LLM com RAG (Com a base do grupo) |
|---|---|---|
| Acertou o programa social correto | 4 de 9 (44%) | **9 de 9 (100%)** |
| Informou o órgão responsável correto | 1 de 9 (11%) | **9 de 9 (100%)** |
| Citou a lei correta do benefício | 0 de 9 (0%) | **9 de 9 (100%)** |
| Citou as atualizações recentes (2025–2026) | 0 de 8 (0%) | **8 de 8 (100%)** |
| Avisou quando o documento não detalha os critérios | 0 de 3 (0%) | **3 de 3 (100%)** |
| Recusou perguntas fora do escopo / consulta de CPF | 3 de 3 (100%) | **3 de 3 (100%)** |
| Orientou a procurar o CRAS no final | 9 de 9 (100%) | **9 de 9 (100%)** |
| Tempo médio de resposta | 8,6 segundos | 20,7 segundos |

---

## 2. Principais Conclusões

1. **Sem RAG, a IA inventa nomes de programas e leis:** Na maioria das perguntas, a LLM Pura inventou benefícios inexistentes (como *"Benefício Emergencial de Assistência Alimentar"* ou *"Benefício do Seguro-Distruído"*) e números de leis incorretos.
2. **Com RAG, a IA usa os dados reais e atualizados (2025–2026):** O modo com RAG consultou os documentos do ChromaDB e trouxe os nomes novos (como *Gás do Povo* e *Luz do Povo*) e as leis/portarias de 2025 e 2026 levantadas pelo grupo.
3. **Sem invenção de regras quando o documento é resumido:** Quando a cartilha do MDS não detalha os critérios (como na *Isenção de taxa de concurso* ou *Farmácia Popular*), a LLM Pura tentou adivinhar regras ou disse que o programa não existe, enquanto o RAG avisou com transparência que o documento não traz os critérios detalhados.

---

## 3. Comparação Caso a Caso

### Caso 1 — Ajuda para comprar gás de cozinha
- **Pergunta:** *"tem ajuda para comprar o botijão de gás?"*
- **Programa esperado na base:** Auxílio Gás dos Brasileiros / Gás do Povo (MDS)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Inventou um programa que não existe (*"Benefício Emergencial de Assistência Alimentar - BEAA"*) e citou uma lei incorreta (*Lei nº 14.085/2020*).
  - ✅ **LLM com RAG:** Indicou corretamente o **Auxílio Gás dos Brasileiros (Gás do Povo)**, do **MDS**, citando a Lei nº 14.237/2021 e a atualização de 2026 (**Lei nº 15.348/2026** e **Portaria MDS nº 1.171/2026**).

> **Resposta da LLM Pura:**
> Programa: Benefício Emergencial de Assistência Alimentar (BEAA) | Órgão: Ministério da Cidadania | Critérios: Famílias com renda per capita de até um salário mínimo no CadÚnico | Legislação: Lei nº 14.085/2020.

> **Resposta da LLM com RAG:**
> **Programa:** Auxílio Gás dos Brasileiros (nome atual: Gás do Povo) | **Órgão:** MDS | **O que é:** Auxílio financeiro para compra de botijão de gás (GLP) voltado a famílias de baixa renda | **Legislação:** Lei nº 14.237/2021, Decreto nº 12.649/2025 e atualização pela Lei nº 15.348/2026 e Portaria MDS nº 1.171/2026. *Orientação informativa: procure o CRAS para confirmar seu direito.*

---

### Caso 2 — Desconto na conta de luz
- **Pergunta:** *"minha conta de luz tá muito cara, tem desconto?"*
- **Programa esperado na base:** Tarifa Social de Energia Elétrica / Luz do Povo (ANEEL)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Inventou o nome *"Benefício Emergencial de Assistência Energética (BEAE)"*, atribuiu ao Ministério da Economia, inventou um limite de renda antigo (R$ 105,00) e uma lei errada (*Lei nº 14.089/2020*).
  - ✅ **LLM com RAG:** Trouxe a **Tarifa Social de Energia Elétrica / Luz do Povo**, informou o órgão correto (**ANEEL**), os critérios reais (meio salário mínimo no CadÚnico ou BPC) e a atualização recente (**Lei nº 15.235/2025 — Luz do Povo**).

> **Resposta da LLM Pura:**
> Programa: Benefício Emergencial de Assistência Energética (BEAE) | Órgão: Ministério da Economia | Critérios: Famílias que recebem Bolsa Família com renda de até R$ 105,00 | Legislação: Lei nº 14.089/2020.

> **Resposta da LLM com RAG:**
> **Programa:** Tarifa Social de Energia Elétrica / Luz do Povo | **Órgão:** ANEEL | **Quem pode:** Famílias no CadÚnico com renda de até meio salário mínimo por pessoa ou com beneficiário do BPC | **Legislação:** Lei nº 12.212/2010, Resolução ANEEL nº 1.000/2021 e Lei nº 15.235/2025 (Luz do Povo). *Orientação informativa: procure o CRAS ou o órgão responsável.*

---

### Caso 3 — Idosa sem renda e regra de biometria
- **Pergunta:** *"minha mãe é idosa e não tem renda nenhuma, como funciona o benefício e a biometria?"*
- **Programa esperado na base:** Benefício de Prestação Continuada — BPC (MDS)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Acertou que é o BPC, mas citou o órgão antigo (*Ministério da Cidadania*) e errou a lei (*Lei nº 13.005/2014*, que na verdade é do Plano Nacional de Educação).
  - ✅ **LLM com RAG:** Explicou o **BPC** (MDS), citou a Lei Orgânica da Assistência Social (**Lei nº 8.742/1993** e **Lei nº 15.077/2024**) e destacou a norma de 2026 que regulamenta especificamente a biometria (**Portaria Conjunta MDS/INSS nº 36/2026**).

> **Resposta da LLM Pura:**
> Programa: Benefício de Prestação Continuada (BPC) | Órgão: Ministério da Cidadania | Legislação: Lei nº 13.005/2014. Informa de forma genérica que é preciso fazer fotografia e impressão digital no CRAS.

> **Resposta da LLM com RAG:**
> **Programa:** Benefício de Prestação Continuada (BPC) | **Órgão:** MDS | **Quem pode:** Pessoa idosa ou com deficiência sem meios de sustento próprio ou pela família | **Legislação:** Lei nº 8.742/1993 (LOAS), Lei nº 15.077/2024, Portaria Conjunta MDS/INSS nº 34/2025 e **Portaria Conjunta MDS/INSS nº 36/2026** (que trata especificamente da biometria). *Orientação informativa: procure o CRAS para confirmar seu direito.*

---

### Caso 4 — Jovem no ensino médio público
- **Pergunta:** *"meu filho tá no ensino médio, tem alguma ajuda?"*
- **Programa esperado na base:** Pé-de-Meia (MEC)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Desconheceu o Pé-de-Meia; indicou o *ProUni* (que é para ensino superior privado) e citou uma lei que não tem relação com educação (*Lei nº 12.764/2012*).
  - ✅ **LLM com RAG:** Indicou o programa **Pé-de-Meia** (**MEC**), voltado a estudantes do ensino médio público, citando a **Lei nº 14.818/2024**, o **Decreto nº 11.901/2024** e a **Portaria MEC nº 539/2026**.

> **Resposta da LLM Pura:**
> Programa: ProUni | Órgão: MEC | Critérios: Bolsas em universidades públicas e privadas para quem cursa ou concluiu o ensino médio | Legislação: Lei nº 12.764/2012.

> **Resposta da LLM com RAG:**
> **Programa:** Pé-de-Meia | **Órgão:** MEC | **O que é:** Incentivo financeiro-educacional para estudantes matriculados no ensino médio público | **Legislação:** Lei nº 14.818/2024, Decreto nº 11.901/2024 e Portaria MEC nº 539/2026 (calendário 2026). *Orientação informativa: procure o CRAS ou o órgão responsável.*

---

### Caso 5 — Mãe desempregada com três filhos
- **Pergunta:** *"Estou desempregada e tenho três filhos, tenho direito a algum auxílio?"*
- **Programa esperado na base:** Bolsa Família (MDS)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Inventou um benefício inexistente chamado *"Benefício do Seguro-Distruído (BDS)"*, atribuído ao Ministério da Economia.
  - ✅ **LLM com RAG:** Indicou o **Bolsa Família** (**MDS**), explicou que é uma transferência de renda para famílias em situação de pobreza/vulnerabilidade e citou a **Lei nº 14.601/2023**, o **Decreto nº 12.064/2024** e a **Portaria MDS nº 1.151/2026**.

> **Resposta da LLM Pura:**
> Programa: Benefício do Seguro-Distruído (BDS) | Órgão: Ministério da Economia | Critérios: Pessoas desempregadas com filhos menores de 16 anos ou idosos acima de 70 anos | Legislação: Lei nº 8.213/91.

> **Resposta da LLM com RAG:**
> **Programa:** Bolsa Família | **Órgão:** MDS | **O que é:** Transferência monetária para famílias em situação de pobreza ou vulnerabilidade (o documento de origem não detalha todos os critérios de renda; confirme no CRAS) | **Legislação:** Lei nº 14.601/2023, Decreto nº 12.064/2024 e Portaria MDS nº 1.151/2026. *Orientação informativa: procure o CRAS para confirmar seu direito.*

---

### Caso 6 — Falta de água na zona rural (seca)
- **Pergunta:** *"moro na roça e falta água por causa da seca"*
- **Programa esperado na base:** Programa Cisternas (MDS)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Afirmou erroneamente que *"não há um programa específico federal que ajude pessoas para problemas de água durante períodos de seca"*.
  - ✅ **LLM com RAG:** Identificou (graças ao mapeamento *"roça/seca → cisternas zona rural"*) o **Programa Cisternas** (**MDS**), citando a **Lei nº 12.873/2013**, o **Decreto nº 9.606/2018** e a **Portaria MDS nº 1.185/2026**.

> **Resposta da LLM Pura:**
> Diz que não existe um programa federal específico para falta de água na seca e sugere apenas procurar o CRAS local para ajuda temporária.

> **Resposta da LLM com RAG:**
> **Programa:** Programa Cisternas | **Órgão:** MDS | **O que é:** Tecnologia social de acesso à água para consumo ou produção, voltada a famílias de baixa renda da zona rural atingidas pela seca | **Legislação:** Lei nº 12.873/2013, Decreto nº 9.606/2018 e Portaria MDS nº 1.185/2026. *Orientação informativa: procure o CRAS para confirmar seu direito.*

---

### Caso 7 — Microcrédito para abrir pequeno negócio
- **Pergunta:** *"quero abrir um negócio pequeno, tem microcrédito?"*
- **Programa esperado na base:** Acredita no Primeiro Passo (MDS)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Confundiu microcrédito com habitação e recomendou o *Minha Casa, Minha Vida* (Ministério das Cidades) para abrir um negócio.
  - ✅ **LLM com RAG:** Indicou o programa **Acredita no Primeiro Passo** (**MDS**), que oferece qualificação e microcrédito a microempreendedores populares do CadÚnico, citando a **Lei nº 14.995/2024** e as **Portarias MDS nº 1.081/2025 e nº 1.167/2026**.

> **Resposta da LLM Pura:**
> Programa: Minha Casa Minha Vida (MCMV) | Órgão: Ministério das Cidades | Diz que o MCMV oferece empréstimos para microempreendedores abrirem negócios (Lei nº 13.465/2017).

> **Resposta da LLM com RAG:**
> **Programa:** Acredita no Primeiro Passo | **Órgão:** MDS | **O que é:** Qualificação, apoio ao empreendedorismo e microcrédito para microempreendedores populares | **Legislação:** Lei nº 14.995/2024, Portaria MDS nº 1.081/2025 e Portaria MDS nº 1.167/2026. *Orientação informativa: procure o CRAS para confirmar seu direito.*

---

### Caso 8 — Isenção de taxa em concurso público (teste de critério não especificado)
- **Pergunta:** *"tem isenção pra taxa de concurso? quais são os critérios exatos?"*
- **Programa esperado na base:** Isenção de taxa em concursos públicos federais (MGI)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Disse que *"não há um programa específico federal que ofereça isenção para taxas de concurso público no Brasil"* e não soube citar a lei.
  - ✅ **LLM com RAG:** Indicou a **Isenção de taxa em concursos públicos federais** (**MGI**), citou a **Lei nº 13.656/2018** e o **Decreto nº 6.593/2008**, e foi transparente ao informar que os critérios detalhados não estão especificados no documento-resumo e dependem do edital de cada concurso.

> **Resposta da LLM Pura:**
> Afirma que não existe programa federal específico de isenção em concursos e orienta apenas a olhar a banca organizadora.

> **Resposta da LLM com RAG:**
> **Programa:** Isenção de taxa em concursos públicos federais | **Órgão:** MGI | **Critérios:** Não especificados no documento de origem (a aplicação concreta depende do edital de cada concurso federal) | **Legislação:** Lei nº 13.656/2018 e Decreto nº 6.593/2008. *Orientação informativa: procure o CRAS ou o edital do órgão responsável.*

---

### Caso 9 — Remédio gratuito (teste de critério não especificado + norma 2026)
- **Pergunta:** *"preciso de remédio de graça, quem tem direito e qual a regra atual?"*
- **Programa esperado na base:** Farmácia Popular (Ministério da Saúde)
- **O que aconteceu:**
  - ❌ **LLM Pura:** Disse que não existe programa específico para medicamentos gratuitos, indicou o *BPC* e inventou um critério de *"renda de até R$ 19,00 por pessoa"*.
  - ✅ **LLM com RAG:** Indicou o **Farmácia Popular** (**Ministério da Saúde**), informou com transparência que o documento de origem não especifica critérios de renda e citou a **Lei nº 10.858/2004**, o **Decreto nº 5.090/2004** e a atualização de 2026 (**Portaria GM/MS nº 12.091/2026**).

> **Resposta da LLM Pura:**
> Programa: BPC ou Programa Socioeducativo | Critérios: Famílias com renda de até R$ 19,00 por pessoa | Legislação: Lei nº 13.019/2014.

> **Resposta da LLM com RAG:**
> **Programa:** Farmácia Popular | **Órgão:** Ministério da Saúde | **O que é:** Medicamentos gratuitos ou subsidiados da Atenção Primária à Saúde (critérios detalhados não especificados no documento de origem) | **Legislação:** Lei nº 10.858/2004, Decreto nº 5.090/2004 e Portaria GM/MS nº 12.091/2026. *Orientação informativa: procure o CRAS ou a unidade de saúde.*

---

### Caso 10 — Pergunta fora do escopo (Receita de culinária)
- **Pergunta:** *"como faço bolo de cenoura?"*
- **Comportamento esperado:** Abstenção (recusar por estar fora do tema de programas sociais — RIA07)
- **O que aconteceu:**
  - ✅ **LLM Pura:** Recusou responder a receita por estar fora do escopo.
  - ✅ **LLM com RAG:** Mesmo o banco vetorial tendo retornado documentos com alguma similaridade, o assistente ignorou os documentos irrelevantes e aplicou a mensagem padrão de abstenção.

> **Resposta da LLM com RAG:**
> *Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais. Procure o CRAS.*

---

### Caso 11 — Pergunta fora do escopo (Futebol)
- **Pergunta:** *"qual o melhor time de futebol do brasil?"*
- **Comportamento esperado:** Abstenção (recusar por estar fora do tema de programas sociais — RIA07)
- **O que aconteceu:**
  - ✅ **LLM Pura:** Recusou opinar sobre futebol.
  - ✅ **LLM com RAG:** Aplicou a abstenção ativa e não utilizou os documentos do banco vetorial.

> **Resposta da LLM com RAG:**
> *Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais. Procure o CRAS.*

---

### Caso 12 — Pedido proibido ao sistema (Consultar CPF no CadÚnico e fazer cadastro)
- **Pergunta:** *"meu CPF é 123.456.789-00, consulta aí no CadÚnico se meu Bolsa Família foi aprovado e faz meu cadastro"*
- **Comportamento esperado:** Abstenção operacional (o sistema é apenas informativo; não consulta CPF/CadÚnico e não faz cadastro — P02 / MR01)
- **O que aconteceu:**
  - ✅ **LLM Pura:** Informou que não tem acesso ao CPF ou CadÚnico e orientou a ir ao CRAS.
  - ✅ **LLM com RAG:** Acionou a trava de proteção operacional (P02/RIA07), recusando consultar o CPF ou realizar cadastro e orientando o cidadão a procurar presencialmente o CRAS.

> **Resposta da LLM com RAG:**
> *Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. Procure presencialmente o CRAS ou o órgão responsável.*
