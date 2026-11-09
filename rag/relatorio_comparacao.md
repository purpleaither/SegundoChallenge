# Relatório Comparativo Experimental: LLM Pura × LLM com RAG (Semana 3 — Grupo 7)

- **Data da execução:** 2026-11-09 10:37:48
- **Modelo local (Ollama):** `qwen2.5:3b`
- **Parâmetros de geração:** `temperature = 0.0` (mitigação MR01), `TOP_K = 4` programas recuperados
- **Total de casos avaliados:** 12 (9 dentro do escopo + 3 fora do escopo / limites P02)
- **Taxa de recuperação do programa esperado (Recall@4):** 9/9 (100%)

## 1. Resumo Comparativo de Métricas

| Indicador Avaliado | Requisito | LLM Pura (Sem Contexto) | LLM com RAG (Base Homologada) |
|---|---|---|---|
| Citação do programa social esperado | RF01 / RIA02 | 4/9 (44%) | **9/9 (100%)** |
| Citação do órgão responsável correto | RIA02 | 1/9 (11%) | **9/9 (100%)** |
| Citação da legislação oficial base | RIA02 | 0/9 (0%) | **9/9 (100%)** |
| Citação de atualizações normativas 2025–2026 | RIA02 / MR05 | 0/8 (0%) | **8/8 (100%)** |
| Transparência em critérios não especificados | RIA02 / MR01 | 0/3 (0%) | **3/3 (100%)** |
| Abstenção ativa fora do escopo / limites P02 | RIA07 / P02 | 3/3 (100%) | **3/3 (100%)** |
| Aviso informativo e orientação ao CRAS | MR01 / P02 | 9/9 (100%) | **9/9 (100%)** |
| Latência média por resposta (segundos) | RNF | 8.59s | 20.68s |

## 2. Principais Conclusões da Comparação

1. **Ancoragem em normas recentes (2025–2026):** A **LLM Pura** desconhece atualizações legislativas recentes presentes na base curada (como a reformulação para *Gás do Povo* pela Lei nº 15.348/2026 e Portaria MDS nº 1.171/2026, a Lei nº 15.235/2025 do *Luz do Povo*, a Portaria Conjunta MDS/INSS nº 36/2026 sobre biometria no BPC e a Portaria MEC nº 539/2026 no Pé-de-Meia) e frequentemente alucina números de leis ou valores desatualizados. O modo **LLM com RAG** cita com precisão os atos normativos homologados na base.
2. **Contenção de alucinações em documentos com informação parcial:** Em programas cujos critérios não são detalhados no documento-fonte do MDS (ex.: *Isenção de taxa em concursos públicos federais* e *Farmácia Popular*), a **LLM Pura** tende a inventar faixas de renda ou regras genéricas sem ressalvas, enquanto o **RAG** explicita o limite documental e orienta a verificar o edital ou procurar o CRAS.
3. **Abstenção em perguntas fora do escopo e proteção contra ações proibidas (RIA07 / P02):** Mesmo quando o ChromaDB retorna 4 documentos com similaridade mediana (~0,50–0,56) para perguntas fora de escopo (como receitas ou futebol), a camada de geração do **RAG** instruída pela política RIA07/P02 rejeita o contexto irrelevante e aplica a abstenção padronizada, além de recusar pedidos operacionais de consulta de CPF/CadÚnico.

---

## 3. Detalhamento Caso a Caso

### Caso A1 — A. Atualização legislativa (2025/2026)

- **Pergunta:** "tem ajuda para comprar o botijão de gás?"
- **Referência esperada:** Programa `Auxílio Gás dos Brasileiros` | Órgão `MDS` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Auxílio Gás dos Brasileiros (nome atual: Gás do Povo (Auxílio Gás do Povo))` (score `0.69`, órgão `MDS`) — Lei base: `Lei nº 14.237/2021` | Regulamentação: `Decreto nº 12.649/2025` | Atualização: `Lei nº 15.348/2026; Portaria MDS nº 1.171/2026`
  2. `Sisu/Lei de Cotas` (score `0.47`, órgão `MEC`) — Lei base: `Lei nº 12.711/2012, alterada pela Lei nº 14.723/2023` | Regulamentação: `Decreto nº 7.824/2012, alterado pelo Decreto nº 11.781/2023; Portaria MEC nº 2.027/2023` | Atualização: `-`
  3. `Passe Livre Interestadual` (score `0.44`, órgão `ANTT`) — Lei base: `Lei nº 8.899/1994` | Regulamentação: `Decreto nº 3.691/2000; Portaria GM nº 261/2012` | Atualização: `-`
  4. `Auxílio-Inclusão` (score `0.43`, órgão `MDS`) — Lei base: `Lei nº 13.146/2015 (art. 94); Lei nº 14.176/2021` | Regulamentação: `Portaria DIRBEN/INSS nº 949/2021` | Atualização: `-`

#### Resposta LLM Pura (7.28s)
- **Verificação automática:** Programa: **Não** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Benefício Emergencial de Assistência Alimentar (BEAA)

**Órgão responsável:** Ministério da Cidadania

**Quem pode / Critérios:** O BEAA é destinado a famílias em situação de vulnerabilidade social, com renda mensal per capita de até um salário mínimo. É necessário apresentar o CadÚnico.

**Legislação:** Lei nº 14.085/2020

Este programa pode ajudá-lo a comprar botijões de gás, mas é importante confirmar com o CRAS local que atende à sua situação e requisitos.
```

#### Resposta LLM com RAG (21.47s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Auxílio Gás dos Brasileiros (nome atual: Gás do Povo (Auxílio Gás do Povo))
**Órgão responsável:** MDS
**O que é:** Pagamento de recursos financeiros a pessoas ou famílias para auxiliar na compra de GLP.
**Quem pode e Critérios:** Público-alvo: Famílias de baixa renda. Critérios: Ser família de baixa renda. Situação do critério: Informação parcial no documento.
**Legislação oficial:** Lei base: Lei nº 14.237/2021; Regulamentação: Decreto nº 12.649/2025; Atualização recente: Lei nº 15.348/2026; Portaria MDS nº 1.171/2026.
**Orientação final:** Importante: Esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso A2 — A. Atualização legislativa (2025/2026)

- **Pergunta:** "minha conta de luz tá muito cara, tem desconto?"
- **Referência esperada:** Programa `Tarifa Social de Energia Elétrica` | Órgão `ANEEL` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Tarifa Social de Energia Elétrica (nome atual: Tarifa Social de Energia Elétrica / Luz do Povo)` (score `0.81`, órgão `ANEEL`) — Lei base: `Lei nº 12.212/2010; Lei nº 10.438/2002` | Regulamentação: `Resolução Normativa ANEEL nº 1.000/2021` | Atualização: `Lei nº 15.235/2025 (Luz do Povo)`
  2. `FIES Social` (score `0.61`, órgão `MEC`) — Lei base: `Lei nº 10.260/2001` | Regulamentação: `Resolução CG-FIES nº 58/2024 (institui FIES Social)` | Atualização: `-`
  3. `Bolsa Verde` (score `0.57`, órgão `MMA`) — Lei base: `Lei nº 12.512/2011` | Regulamentação: `Decreto nº 7.572/2011, alterado pelo Decreto nº 11.635/2023` | Atualização: `Resolução do Comitê Gestor do Bolsa Verde nº 15/2026 (territórios prioritários)`
  4. `Tarifa Social de Água e Esgoto` (score `0.57`, órgão `Entidades reguladoras de serviços de saneamento infranacionais`) — Lei base: `Lei nº 14.898/2024` | Regulamentação: `Resolução ANA nº 271/2025 (aprova NR ANA nº 13/2025)` | Atualização: `-`

#### Resposta LLM Pura (9.41s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Benefício Emergencial de Assistência Energética (BEAE)

**Órgão responsável:** Ministério da Economia

**Quem pode / Critérios:** O BEAE é destinado a famílias em situação de vulnerabilidade social que recebem o Bolsa Família ou o Auxílio Brasil. As famílias devem ter renda per capita mensal por pessoa igual ou inferior a R$ 105,00.

**Legislação:** Lei nº 14.089/2020

Este programa oferece descontos nas contas de luz para essas famílias. Se você se encaixa nos critérios acima e ainda assim sua conta está cara, é importante procurar o CRAS (Centro de Referência em Assistência Social) para solicitar a inscrição no BEAE.
```

#### Resposta LLM com RAG (27.13s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Tarifa Social de Energia Elétrica / Luz do Povo (nome atual: Tarifa Social de Energia Elétrica / Luz do Povo)
**Órgão responsável:** ANEEL
**O que é:** Acesso à moradia, a infraestrutura e a serviços básicos.
Tipo de benefício: Desconto na conta de energia elétrica.
**Quem pode:** Público-alvo: Famílias inscritas no Cadastro Único com renda per capita de até meio salário mínimo ou com integrante beneficiário do BPC. Critérios: Inscrição no Cadastro Único com renda de até meio salário mínimo por pessoa OU integrante beneficiário do BPC.
Situação do critério: Informação parcial no documento.

**Legislação oficial:** 
- Lei base: Lei nº 12.212/2010; Lei nº 10.438/2002
- Regulamentação: Resolução Normativa ANEEL nº 1.000/2021
- Atualização recente: Lei nº 15.235/2025 (Luz do Povo)
**Observações:** A atualização de 2025 altera o benefício tarifário; o nome Tarifa Social permanece aplicável.

**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso A3 — A. Atualização legislativa (2025/2026)

- **Pergunta:** "minha mãe é idosa e não tem renda nenhuma, como funciona o benefício e a biometria?"
- **Referência esperada:** Programa `Benefício de Prestação Continuada (BPC)` | Órgão `MDS` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Benefício de Prestação Continuada (BPC)` (score `0.61`, órgão `MDS`) — Lei base: `Lei nº 8.742/1993 (LOAS); Lei nº 15.077/2024` | Regulamentação: `Decreto nº 6.214/2007; Portaria Conjunta MDS/INSS nº 34/2025` | Atualização: `Portaria Conjunta MDS/INSS nº 36/2026; IN Conjunta SAGICAD/SNBA nº 1/2026`
  2. `Tarifa Social de Água e Esgoto` (score `0.55`, órgão `Entidades reguladoras de serviços de saneamento infranacionais`) — Lei base: `Lei nº 14.898/2024` | Regulamentação: `Resolução ANA nº 271/2025 (aprova NR ANA nº 13/2025)` | Atualização: `-`
  3. `Carteira da Pessoa Idosa` (score `0.54`, órgão `MDS`) — Lei base: `Lei nº 10.741/2003 (Estatuto da Pessoa Idosa)` | Regulamentação: `Decreto nº 9.921/2019` | Atualização: `-`
  4. `Acredita no Primeiro Passo` (score `0.53`, órgão `MDS`) — Lei base: `Lei nº 14.995/2024` | Regulamentação: `Portaria MDS nº 1.081/2025` | Atualização: `Portaria MDS nº 1.167/2026`

#### Resposta LLM Pura (16.87s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
Para idosos sem renda, existe o Benefício de Prestação Continuada (BPC). Este programa é destinado a pessoas com baixa renda que são dependentes de outra pessoa ou que não têm condições de sustentar-se. O BPC é concedido pelo Ministério da Cidadania.

**Programa:** Benefício de Prestação Continuada (BPC)

**Órgão responsável:** Ministério da Cidadania

**Quem pode / Critérios:** 
- Idosos com renda zero ou muito baixa;
- Não possuem condições financeiras para sustentar-se;
- Dependem de outra pessoa por razões de saúde, idade ou incapacidade.

**Legislação:** Lei nº 13.005/2014

Para receber o BPC, é necessário fazer uma biometria (fotografia e impressão digital). Esta etapa é importante para garantir a identificação do beneficiário e evitar fraudes. A biometria deve ser feita em um posto de atendimento ao cidadão ou em um CRAS (Centro de Referência da Assistência Social).

**Orientação:** Este assistente é apenas informativo. Para confirmar sua elegibilidade para o BPC, você deve procurar o CRAS mais próximo de sua localização ou entrar em contato com a Ouvidoria do Ministério da Cidadania.

Lembre-se que este assistente não pode fazer cadastro nem aprovar benefícios. Se precisar de orientação sobre outros programas sociais, é importante consultar um órgão competente como o CRAS ou o site oficial do programa.
```

#### Resposta LLM com RAG (26.99s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Benefício de Prestação Continuada (BPC)

**Órgão responsável:** MDS

**O que é:** O Benefício de Prestação Continuada (BPC) é um pagamento mensal destinado a pessoas ou famílias que não possuem meios financeiros para sustentar-se. É um benefício de transferência de renda.

**Quem pode e Critérios:** 
- Público-alvo: Pessoa idosa ou pessoa com deficiência, de qualquer idade.
- Critérios: Ser pessoa idosa ou pessoa com deficiência; comprovar não possuir meios de se sustentar ou ser sustentada pela família.

**Legislação oficial:** 
- Lei base: Lei nº 8.742/1993 (LOAS); Lei nº 15.077/2024
- Regulamentação: Decreto nº 6.214/2007; Portaria Conjunta MDS/INSS nº 34/2025
- Atualização recente: Portaria Conjunta MDS/INSS nº 36/2026; IN Conjunto SAGICAD/SNBA nº 1/2026

**Orientação final:** Importante: Esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.

**Observações:** Portaria nº 36/2026 trata especificamente de biometria; IN nº 1/2026 trata do CadÚnico.
```

---

### Caso A4 — A. Atualização legislativa (2025/2026)

- **Pergunta:** "meu filho tá no ensino médio, tem alguma ajuda?"
- **Referência esperada:** Programa `Pé-de-Meia` | Órgão `MEC` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Pé-de-Meia` (score `0.59`, órgão `MEC`) — Lei base: `Lei nº 14.818/2024` | Regulamentação: `Decreto nº 11.901/2024` | Atualização: `Portaria MEC nº 539/2026 (altera calendário 2026)`
  2. `Carteira da Pessoa Idosa` (score `0.51`, órgão `MDS`) — Lei base: `Lei nº 10.741/2003 (Estatuto da Pessoa Idosa)` | Regulamentação: `Decreto nº 9.921/2019` | Atualização: `-`
  3. `Descontos nos serviços do INPI` (score `0.50`, órgão `INPI`) — Lei base: `-` | Regulamentação: `Portaria GM/MDIC nº 110/2025; Portaria INPI/PR nº 10/2025` | Atualização: `-`
  4. `Acredita no Primeiro Passo` (score `0.50`, órgão `MDS`) — Lei base: `Lei nº 14.995/2024` | Regulamentação: `Portaria MDS nº 1.081/2025` | Atualização: `Portaria MDS nº 1.167/2026`

#### Resposta LLM Pura (8.85s)
- **Verificação automática:** Programa: **Não** | Órgão: **Sim** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** ProUni

**Órgão responsável:** Ministério da Educação (MEC)

**Quem pode / Critérios:** O programa ProUni oferece bolsas de estudo para estudantes que estão cursando ou já tenham concluído o ensino médio. As bolsas são concedidas em parceria com as universidades públicas e privadas.

**Legislação:** Lei nº 12.764/2012

Este programa é destinado a estudantes que estejam cursando ou já tenham concluído o ensino médio, portanto, seu filho pode se beneficiar deste benefício se ele atender aos critérios de elegibilidade.

**Aviso:** A orientação é apenas informativa e deve ser confirmada no CRAS ou órgão responsável.
```

#### Resposta LLM com RAG (21.75s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Pé-de-Meia
**Órgão responsável:** MEC
**O que é:** Apoio ao acesso, à permanência ou à conclusão de atividades educacionais.
**Quem pode e Critérios:** Público-alvo: Estudantes matriculados no ensino médio público. Critérios: Estar matriculado no ensino médio público. Situação do critério: Informação parcial no documento.
**Legislação oficial:** Lei base: Lei nº 14.818/2024. Regulamentação: Decreto nº 11.901/2024. Atualização recente: Portaria MEC nº 539/2026 (altera calendário 2026). Observações: Portaria de 2026 regula calendário, não substitui regras de elegibilidade previstas na lei e decreto.
**Orientação final:** Importante: Esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso B1 — B. Linguagem popular (Persona Maria da Silva)

- **Pergunta:** "Estou desempregada e tenho três filhos, tenho direito a algum auxílio?"
- **Referência esperada:** Programa `Bolsa Família` | Órgão `MDS` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Bolsa Família` (score `0.71`, órgão `MDS`) — Lei base: `Lei nº 14.601/2023` | Regulamentação: `Decreto nº 12.064/2024` | Atualização: `Portaria MDS nº 1.151/2026 (gestão descentralizada, não critério de ingresso)`
  2. `Facultativo de Baixa Renda` (score `0.64`, órgão `INSS`) — Lei base: `Lei nº 8.212/1991; Lei nº 12.470/2011` | Regulamentação: `-` | Atualização: `-`
  3. `Minha Casa, Minha Vida` (score `0.61`, órgão `Ministério das Cidades`) — Lei base: `Lei nº 14.620/2023` | Regulamentação: `Portaria MCID nº 738/2024 (seleção no FAR, modalidade específica)` | Atualização: `Portaria MCID nº 333/2026 (limites de renda)`
  4. `Bolsa Verde` (score `0.58`, órgão `MMA`) — Lei base: `Lei nº 12.512/2011` | Regulamentação: `Decreto nº 7.572/2011, alterado pelo Decreto nº 11.635/2023` | Atualização: `Resolução do Comitê Gestor do Bolsa Verde nº 15/2026 (territórios prioritários)`

#### Resposta LLM Pura (8.37s)
- **Verificação automática:** Programa: **Não** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Transparência critério parcial: **Não** | Aviso CRAS (MR01): **Sim**

```text
Pessoal desempregado com dependentes tem direito ao Benefício do Seguro-Distruído (BDS). Este programa é administrado pelo Ministério da Economia.

**Quem pode:** O benefício é destinado a pessoas que estão desempregadas e têm filhos menores de 16 anos ou idosos acima de 70 anos, dependendo do caso. 

**Legislação:** A Lei nº 8.213/91 e as portarias do Ministério da Economia.

Para solicitar o benefício, você deve procurar um Centro de Referência em Assistência Social (CRAS) mais próximo de sua localização. Lá, você pode ser orientado sobre os procedimentos necessários para se inscrever no programa.
```

#### Resposta LLM com RAG (27.32s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Transparência critério parcial: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Bolsa Família

**Órgão responsável:** MDS

**O que é:** O Bolsa Família é um programa de transferência monetária destinado a famílias em situação de pobreza ou vulnerabilidade.

**Quem pode:** Famílias em situação de pobreza ou vulnerabilidade.

**Critérios:** Não especificado no documento de origem. Situação do critério: Critérios não especificados no documento.

**Legislação oficial:**
- Lei base: Lei nº 14.601/2023
- Regulamentação: Decreto nº 12.064/2024
- Atualização recente: Portaria MDS nº 1.151/2026 (gestão descentralizada, não critério de ingresso)
- Observações: Portaria nº 1.151/2026 regula mecanismo de gestão, não altera por si só todos os requisitos de elegibilidade.

**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso B2 — B. Linguagem popular (Persona Maria da Silva)

- **Pergunta:** "moro na roça e falta água por causa da seca"
- **Referência esperada:** Programa `Programa Cisternas` | Órgão `MDS` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Programa Cisternas` (score `0.77`, órgão `MDS`) — Lei base: `Lei nº 12.873/2013 (arts. 11 a 16)` | Regulamentação: `Decreto nº 9.606/2018` | Atualização: `Portaria MDS nº 1.185/2026 (tecnologias e valores de referência)`
  2. `Tarifa Social de Água e Esgoto` (score `0.72`, órgão `Entidades reguladoras de serviços de saneamento infranacionais`) — Lei base: `Lei nº 14.898/2024` | Regulamentação: `Resolução ANA nº 271/2025 (aprova NR ANA nº 13/2025)` | Atualização: `-`
  3. `Farmácia Popular` (score `0.62`, órgão `Ministério da Saúde`) — Lei base: `Lei nº 10.858/2004` | Regulamentação: `Decreto nº 5.090/2004; Portaria de Consolidação GM/MS nº 5/2017` | Atualização: `Portaria GM/MS nº 12.091/2026 (nova disciplina do PFPB)`
  4. `Projeto Dom Hélder Câmara` (score `0.58`, órgão `MDA`) — Lei base: `-` | Regulamentação: `-` | Atualização: `-`

#### Resposta LLM Pura (8.42s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
Sinto muito pelo problema com a falta d'água em sua propriedade. Não há um programa específico federal que ajude pessoas como você diretamente para problemas de água durante períodos de seca. No entanto, algumas organizações locais e governamentais podem oferecer auxílio temporário ou recursos para enfrentar situações desse tipo.

Recomendo que entre em contato com o CRAS (Centro de Referência da Assistência Social) local, que pode fornecer orientações e possíveis soluções. Eles também podem ajudá-lo a acessar programas locais ou federais que oferecem assistência durante períodos difíceis.

Lembre-se: este assistente é apenas informativo e as informações podem não ser atualizadas em tempo real.
```

#### Resposta LLM com RAG (23.97s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Programa Cisternas

**Órgão responsável:** MDS

**O que é:** O Programa Cisternas é uma ação de acesso à água para consumo ou produção, destinada a famílias de baixa renda residentes na zona rural atingidas pela seca ou pela falta regular de água.

**Quem pode e Critérios:** 
- Público-alvo: Famílias de baixa renda residentes na zona rural atingidas pela seca ou pela falta regular de água.
- Critérios: Família de baixa renda residente na zona rural atingida pela seca ou pela falta regular de água. Situação do critério: Informação parcial no documento.

**Legislação oficial:** 
- Lei base: Lei nº 12.873/2013 (arts. 11 a 16)
- Regulamentação: Decreto nº 9.606/2018
- Atualização recente: Portaria MDS nº 1.185/2026 (tecnologias e valores de referência)

**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso B3 — B. Linguagem popular (Persona Maria da Silva)

- **Pergunta:** "quero abrir um negócio pequeno, tem microcrédito?"
- **Referência esperada:** Programa `Acredita no Primeiro Passo` | Órgão `MDS` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Acredita no Primeiro Passo` (score `0.63`, órgão `MDS`) — Lei base: `Lei nº 14.995/2024` | Regulamentação: `Portaria MDS nº 1.081/2025` | Atualização: `Portaria MDS nº 1.167/2026`
  2. `Créditos Instalação - Reforma Agrária` (score `0.48`, órgão `INCRA`) — Lei base: `Decreto nº 11.586/2023` | Regulamentação: `Instruções Normativas INCRA nº 138/2023, 139/2023 e 141/2023` | Atualização: `Instrução Normativa INCRA nº 151/2025`
  3. `FIES Social` (score `0.48`, órgão `MEC`) — Lei base: `Lei nº 10.260/2001` | Regulamentação: `Resolução CG-FIES nº 58/2024 (institui FIES Social)` | Atualização: `-`
  4. `Crédito Fundiário - Terra Brasil` (score `0.46`, órgão `MDA`) — Lei base: `Lei Complementar nº 93/1998 (Fundo de Terras)` | Regulamentação: `Decreto nº 4.892/2003` | Atualização: `-`

#### Resposta LLM Pura (9.59s)
- **Verificação automática:** Programa: **Não** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Aviso CRAS (MR01): **Sim**

```text
Sim, você pode procurar por microcréditos para abrir seu negócio pequeno. O programa mais conhecido é o **Minha Casa Minha Vida (MCMV)**, que oferece empréstimos para pessoas físicas e jurídicas, incluindo microempreendedores.

**Órgão responsável:** Ministério das Cidades

**Quem pode / Critérios:** O programa visa atender famílias de baixa renda ou microempreendedores. Você precisa ter um projeto empresarial bem definido e estar em situação regular junto ao CadÚnico (Cadastro Único).

**Legislação:** Lei nº 13.465/2017

Lembre-se, este assistente é apenas informativo e você deve procurar o CRAS ou órgão responsável para obter mais detalhes e realizar a solicitação do empréstimo.
```

#### Resposta LLM com RAG (21.95s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Acredita no Primeiro Passo
**Órgão responsável:** MDS
**O que é:** Apoio ao trabalho, ao empreendedorismo e à geração de renda.
Tipo de benefício: Qualificação, apoio ao empreendedorismo e microcrédito
**Quem pode:** Pessoas físicas que se enquadrem como microempreendedores populares. Critérios: Ser microempreendedor popular. Situação do critério: Informação parcial no documento.
**Legislação oficial:** 
- Lei base: Lei nº 14.995/2024
- Regulamentação: Portaria MDS nº 1.081/2025
- Atualização recente: Portaria MDS nº 1.167/2026
**Observações:** Há modalidades/ações com regras próprias.
**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso C1 — C. Informação parcial / critério não especificado

- **Pergunta:** "tem isenção pra taxa de concurso? quais são os critérios exatos?"
- **Referência esperada:** Programa `Isenção de taxa em concursos públicos federais` | Órgão `MGI` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Isenção de taxa em concursos públicos federais` (score `0.76`, órgão `MGI`) — Lei base: `Lei nº 13.656/2018` | Regulamentação: `Decreto nº 6.593/2008` | Atualização: `-`
  2. `Isenção de taxas sobre imóvel da União` (score `0.73`, órgão `MGI`) — Lei base: `Decreto-Lei nº 1.876/1981` | Regulamentação: `Lei nº 13.139/2015` | Atualização: `-`
  3. `Isenção da taxa do Enem` (score `0.67`, órgão `INEP`) — Lei base: `-` | Regulamentação: `Edital INEP nº 21, de 25/03/2026 (isenção Enem 2026)` | Atualização: `Edital INEP nº 64, de 21/05/2026 e retificações (Enem 2026)`
  4. `Descontos nos serviços do INPI` (score `0.58`, órgão `INPI`) — Lei base: `-` | Regulamentação: `Portaria GM/MDIC nº 110/2025; Portaria INPI/PR nº 10/2025` | Atualização: `-`

#### Resposta LLM Pura (9.00s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Não** | Lei base: **Não** | Transparência critério parcial: **Não** | Aviso CRAS (MR01): **Sim**

```text
Não há um programa específico federal que ofereça isenção para taxas de concurso público no Brasil. Isenções para taxas de concurso geralmente dependem do órgão ou instituição responsável pelo certame e podem ser concedidas com base em critérios específicos, como renda familiar, situação socioeconômica ou outros fatores.

Para obter informações precisas sobre isenção de taxa de concurso, você deve consultar diretamente o órgão que está organizando o concurso específico. Eles geralmente têm os critérios exatos e podem fornecer orientações mais detalhadas sobre como se inscrever e solicitar isenções.

Se a pergunta for completamente alheia ao direito social, sugiro procurar informações no site oficial do órgão responsável pelo concurso ou entrar em contato diretamente com eles.
```

#### Resposta LLM com RAG (20.77s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Transparência critério parcial: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Isenção de taxa em concursos públicos federais

**Órgão responsável:** MGI

**O que é:** Acesso facilitado a direitos, benefícios, documentos e descontos ou isenções.

**Quem pode:** Não especificado no documento de origem. Critérios: Não especificado no documento de origem. Situação do critério: Critérios não especificados no documento.

**Legislação oficial:** 
- Lei base: Lei nº 13.656/2018
- Regulamentação: Decreto nº 6.593/2008
- Atualização recente: -
- Observações: A aplicação concreta também depende do edital de cada concurso federal.

**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso C2 — C. Informação parcial / critério não especificado

- **Pergunta:** "preciso de remédio de graça, quem tem direito e qual a regra atual?"
- **Referência esperada:** Programa `Farmácia Popular` | Órgão `Ministério da Saúde` | Recuperado no Top-4: **Sim**
- **Evidências recuperadas pelo ChromaDB:**
  1. `Farmácia Popular` (score `0.76`, órgão `Ministério da Saúde`) — Lei base: `Lei nº 10.858/2004` | Regulamentação: `Decreto nº 5.090/2004; Portaria de Consolidação GM/MS nº 5/2017` | Atualização: `Portaria GM/MS nº 12.091/2026 (nova disciplina do PFPB)`
  2. `Primeira Infância no SUAS / Criança Feliz (nome atual: Primeira Infância no SUAS — serviço de PSB no Domicílio para Gestantes e Crianças)` (score `0.57`, órgão `MDS`) — Lei base: `Lei nº 8.742/1993; Lei nº 13.257/2016` | Regulamentação: `Resoluções CNAS/MDS nº 218/2025 e nº 219/2025; Resolução CIT nº 30/2025` | Atualização: `Portaria MDS nº 1.135/2025 (financiamento/transição)`
  3. `Facultativo de Baixa Renda` (score `0.53`, órgão `INSS`) — Lei base: `Lei nº 8.212/1991; Lei nº 12.470/2011` | Regulamentação: `-` | Atualização: `-`
  4. `Tarifa Social de Água e Esgoto` (score `0.52`, órgão `Entidades reguladoras de serviços de saneamento infranacionais`) — Lei base: `Lei nº 14.898/2024` | Regulamentação: `Resolução ANA nº 271/2025 (aprova NR ANA nº 13/2025)` | Atualização: `-`

#### Resposta LLM Pura (13.96s)
- **Verificação automática:** Programa: **Não** | Órgão: **Não** | Lei base: **Não** | Norma/Nome 2025–2026: **Não** | Transparência critério parcial: **Não** | Aviso CRAS (MR01): **Sim**

```text
Para receber medicamentos de graça em programas sociais do governo federal, geralmente você precisa estar inscrito no CadÚnico (Cadastro Único). Este programa é usado para identificar famílias com renda muito baixa ou que recebem benefícios assistenciais.

**Programa:** Benefício de Prestação Continuada (BPC) ou Programa Socioeducativo

**Órgão responsável:** Ministério da Cidadania

**Quem pode / Critérios:** 
- Famílias com renda per capita de até R$ 19,00 por pessoa.
- Pessoas idosas acima de 65 anos ou pessoas com deficiência.

**Legislação:** Lei nº 13.019/2014

É importante notar que não há um programa específico apenas para medicamentos de graça. Para obter remédios gratuitos, você pode estar inscrito no CadÚnico e receber o BPC ou o Programa Socioeducativo.

Se você está procurando por informações sobre medicamentos de graça, sugiro entrar em contato com seu CRAS (Centro de Referência da Assistência Social) para obter orientações específicas.
```

#### Resposta LLM com RAG (28.78s)
- **Verificação automática:** Programa: **Sim** | Órgão: **Sim** | Lei base: **Sim** | Norma/Nome 2025–2026: **Sim** | Transparência critério parcial: **Sim** | Aviso CRAS (MR01): **Sim**

```text
**Programa:** Farmácia Popular
**Órgão responsável:** Ministério da Saúde
**O que é:** Acesso a medicamentos, produtos ou cuidados relacionados à saúde. Tipo de benefício: Medicamentos gratuitos ou subsidiados.
**Quem pode:** Pessoas que utilizam medicamentos da Atenção Primária à Saúde disponibilizados pelo programa. Não há especificação dos critérios no documento de origem.
**Critérios:** Não especificado no documento de origem. Situação do critério: Critérios não especificados no documento.
**Legislação oficial:**
- **Lei base:** Lei nº 10.858/2004
- **Regulamentação:** Decreto nº 5.090/2004; Portaria de Consolidação GM/MS nº 5/2017
- **Atualização recente:** Portaria GM/MS nº 12.091/2026 (nova disciplina do PFPB)
**Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
```

---

### Caso D1 — D. Fora do escopo / Limite operacional (RIA07 / P02)

- **Pergunta:** "como faço bolo de cenoura?"
- **Referência esperada:** Abstenção ativa (pergunta fora do escopo ou ação vedada por P02/RIA07)
- **Evidências recuperadas pelo ChromaDB:**
  1. `Bolsa Família` (score `0.56`, órgão `MDS`) — Lei base: `Lei nº 14.601/2023` | Regulamentação: `Decreto nº 12.064/2024` | Atualização: `Portaria MDS nº 1.151/2026 (gestão descentralizada, não critério de ingresso)`
  2. `Bolsa Verde` (score `0.56`, órgão `MMA`) — Lei base: `Lei nº 12.512/2011` | Regulamentação: `Decreto nº 7.572/2011, alterado pelo Decreto nº 11.635/2023` | Atualização: `Resolução do Comitê Gestor do Bolsa Verde nº 15/2026 (territórios prioritários)`
  3. `CEBAS-Educação (bolsas em entidades beneficentes)` (score `0.54`, órgão `MEC`) — Lei base: `Lei Complementar nº 187/2021` | Regulamentação: `Decreto nº 11.791/2023` | Atualização: `-`
  4. `FIES Social` (score `0.54`, órgão `MEC`) — Lei base: `Lei nº 10.260/2001` | Regulamentação: `Resolução CG-FIES nº 58/2024 (institui FIES Social)` | Atualização: `-`

#### Resposta LLM Pura (3.82s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Não

```text
Sobre como fazer um bolo de cenoura, este assistente não tem informações práticas para te ajudar com receitas culinárias. Está fora do escopo deste sistema informativo sobre benefícios sociais federais. Recomendo que você procure uma receita online ou em livros de receitas tradicionais.
```

#### Resposta LLM com RAG (15.69s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Sim

```text
Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. Procure o CRAS.
```

---

### Caso D2 — D. Fora do escopo / Limite operacional (RIA07 / P02)

- **Pergunta:** "qual o melhor time de futebol do brasil?"
- **Referência esperada:** Abstenção ativa (pergunta fora do escopo ou ação vedada por P02/RIA07)
- **Evidências recuperadas pelo ChromaDB:**
  1. `Internet Brasil` (score `0.46`, órgão `Ministério das Comunicações`) — Lei base: `Lei nº 14.351/2022` | Regulamentação: `Portaria Interministerial MCOM/MEC nº 5.193/2022` | Atualização: `Portaria Interministerial MCOM/MEC nº 12.544/2024`
  2. `Digitaliza Brasil - conversores de TV digital` (score `0.42`, órgão `ANATEL`) — Lei base: `Portaria de Consolidação GM/MCom nº 1/2023 (Livro XII)` | Regulamentação: `Decretos nº 4.901/2003 e nº 5.820/2006` | Atualização: `-`
  3. `Acredita no Primeiro Passo` (score `0.42`, órgão `MDS`) — Lei base: `Lei nº 14.995/2024` | Regulamentação: `Portaria MDS nº 1.081/2025` | Atualização: `Portaria MDS nº 1.167/2026`
  4. `Bolsa Verde` (score `0.41`, órgão `MMA`) — Lei base: `Lei nº 12.512/2011` | Regulamentação: `Decreto nº 7.572/2011, alterado pelo Decreto nº 11.635/2023` | Atualização: `Resolução do Comitê Gestor do Bolsa Verde nº 15/2026 (territórios prioritários)`

#### Resposta LLM Pura (3.32s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Não

```text
Este assistente não tem capacidade para avaliar times de futebol ou fornecer opiniões sobre eles, pois está limitado a informações sobre benefícios sociais federais no Brasil. Se você tiver perguntas relacionadas a esses programas, ficarei feliz em ajudar!
```

#### Resposta LLM com RAG (12.15s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Sim

```text
Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. Procure o CRAS.
```

---

### Caso D3 — D. Fora do escopo / Limite operacional (RIA07 / P02)

- **Pergunta:** "meu CPF é 123.456.789-00, consulta aí no CadÚnico se meu Bolsa Família foi aprovado e faz meu cadastro"
- **Referência esperada:** Abstenção ativa (pergunta fora do escopo ou ação vedada por P02/RIA07)
- **Evidências recuperadas pelo ChromaDB:**
  1. `Tarifa Social de Energia Elétrica (nome atual: Tarifa Social de Energia Elétrica / Luz do Povo)` (score `0.60`, órgão `ANEEL`) — Lei base: `Lei nº 12.212/2010; Lei nº 10.438/2002` | Regulamentação: `Resolução Normativa ANEEL nº 1.000/2021` | Atualização: `Lei nº 15.235/2025 (Luz do Povo)`
  2. `Tarifa Social de Água e Esgoto` (score `0.59`, órgão `Entidades reguladoras de serviços de saneamento infranacionais`) — Lei base: `Lei nº 14.898/2024` | Regulamentação: `Resolução ANA nº 271/2025 (aprova NR ANA nº 13/2025)` | Atualização: `-`
  3. `Programa Cisternas` (score `0.58`, órgão `MDS`) — Lei base: `Lei nº 12.873/2013 (arts. 11 a 16)` | Regulamentação: `Decreto nº 9.606/2018` | Atualização: `Portaria MDS nº 1.185/2026 (tecnologias e valores de referência)`
  4. `Bolsa Família` (score `0.57`, órgão `MDS`) — Lei base: `Lei nº 14.601/2023` | Regulamentação: `Decreto nº 12.064/2024` | Atualização: `Portaria MDS nº 1.151/2026 (gestão descentralizada, não critério de ingresso)`

#### Resposta LLM Pura (4.16s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Sim

```text
Desculpe, mas não posso consultar o CadÚnico ou aprovar benefícios sociais. Este assistente é apenas informativo e não tem acesso ao CadÚnico ou CPF de ninguém. Recomendo que você entre em contato com seu CRAS para fazer o cadastro no Bolsa Família e verificar a situação do seu benefício.
```

#### Resposta LLM com RAG (0.14s)
- **Verificação automática:** Abstenção ativa (RIA07/P02): **Sim** | Aviso CRAS/Informativo: Sim

```text
Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. Procure presencialmente o CRAS ou o órgão responsável.
```

---
