# Verificação da abstenção no Ollama

Modelo: `qwen2.5:3b`. Mesmos 25 casos da bateria histórica.

- Fora do escopo: 4/4 abstenções (histórico: 1/4).
- Dentro do escopo: 21/21 não respostas.

A política atual apresentou excesso de abstenção e não está validada para uso. A maioria das recusas decorreu da checagem de evidências pelo modelo pequeno, mesmo diante de programas pertinentes. As decisões estruturadas representam o comportamento do pipeline; não são julgamentos independentes de qualidade.

A primeira tentativa foi preservada em `amostras_abstencao.jsonl`. Após exigir esquema JSON com categorias fixas e simplificar o classificador, a segunda foi salva em `amostras_abstencao_v2.jsonl`. Não foram recalculadas as métricas RAGAS.

| Caso | Decisão | Motivo |
|---|---|---|
| dentro-1 | sem_evidencia | Os documentos fornecidos mencionam programas que podem ser relevantes para a situação descrita, mas não especificam diretamente se o solicitante está apto a receber algum desses benefícios. |
| dentro-2 | sem_evidencia | apenas um documento menciona gás, mas não ajuda a comprar botijão de gás |
| dentro-3 | sem_evidencia | Os documentos fornecidos não mencionam diretamente um programa de desconto na conta de luz. No entanto, o Documento 1 menciona um programa chamado Tarifa Social de Energia Elétrica que pode ser relevante. |
| dentro-4 | sem_evidencia | Os documentos 1 e 3 mencionam programas relacionados a descontos na conta de água ou energia elétrica. No entanto, não há informações específicas sobre se esses descontos são ativos ou disponíveis para uso atual. |
| dentro-5 | sem_evidencia | nenhum documento fornece informações específicas sobre a situação da pergunta |
| dentro-6 | sem_evidencia | Os documentos fornecidos mencionam programas relacionados a benefícios para pessoas com deficiência ou idosos. No entanto, nenhum deles explicitamente menciona um programa específico para crianças e adolescentes com deficiência. |
| dentro-7 | sem_evidencia | Os documentos mencionam programas de assistência estudantil e apoio ao empreendedorismo, mas não abordam diretamente programas de financiamento ou bolsas para faculdade. |
| dentro-8 | sem_evidencia | nenhum dos documentos fornece informações sobre como obter isenção da taxa do Enem |
| dentro-9 | sem_evidencia | nenhum documento menciona isenção para concursos públicos federais |
| dentro-10 | sem_evidencia | Os documentos fornecidos não mencionam nenhum programa específico para o ensino médio. O único documento relacionado ao ensino médio é sobre o Pé-de-Meia, que é um apoio financeiro educacional. |
| dentro-11 | sem_evidencia | Os outros documentos não mencionam programas relacionados a compra de casas |
| dentro-12 | sem_evidencia | Os documentos fornecidos não mencionam remédios ou medicamentos gratuitos |
| dentro-13 | sem_evidencia | O documento mais relevante menciona um programa de distribuição gratuita de absorventes, mas não fornece informações sobre onde esses absorventes podem ser obtidos gratuitamente. |
| dentro-14 | sem_evidencia | O documento 1 menciona programas relacionados a acesso à água para consumo ou produção, mas não aborda diretamente o problema de falta de água por causa da seca na zona rural |
| dentro-15 | sem_evidencia | Os documentos fornecidos não mencionam diretamente como se tornar dona de casa e pagar o INSS mais barato. Os documentos abordam programas governamentais relacionados a habitação, benefícios previdenciários, acesso à água e pagamentos por serviços ambientais. |
| dentro-16 | fora_do_escopo | A pergunta aborda transporte público, não se relacionando diretamente com benefícios sociais ou necessidades cotidianas. |
| dentro-17 | sem_evidencia | apenas um documento menciona microcrédito |
| dentro-18 | sem_evidencia | o documento mais próximo da pergunta contém informações sobre programas que fornecem conectividade ou recursos digitais para a educação |
| dentro-19 | sem_evidencia | Os documentos fornecidos falam sobre programas federais que oferecem benefícios financeiros ou de infraestrutura para famílias, mas não mencionam nenhum programa específico relacionado a cesta de alimentos para famílias passando fome. |
| dentro-20 | sem_evidencia | Os documentos fornecidos não mencionam nenhum programa de acompanhamento para grávidas ou bebês |
| dentro-21 | sem_evidencia | apenas um documento menciona benefícios para mães solteiras de baixa renda, embora não seja específico |
| fora-1 | fora_do_escopo | o usuário fez uma pergunta sobre futebol, que está fora do escopo de dúvidas relacionadas a benefícios sociais ou necessidades básicas. |
| fora-2 | fora_do_escopo | A pergunta é sobre receita de bolo, que não se enquadra em benefícios sociais ou necessidades cotidianas. |
| fora-3 | fora_do_escopo | A pergunta é sobre previsão meteorológica e não se enquadra em nenhum dos tópicos relacionados a benefícios sociais ou necessidades básicas mencionados. |
| fora-4 | fora_do_escopo | A pergunta pede uma recomendação de filme, que está fora do escopo de benefícios sociais ou necessidades cotidianas. |
