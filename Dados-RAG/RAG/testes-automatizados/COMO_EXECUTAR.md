# TESTES AUTOMATIZADOS E AVALIAÇÃO RAGAS

Execute os comandos abaixo na raiz do repositório, no PowerShell.

> **Como escolher o comando em cada etapa:** <br>
> **Opção 1 (`python`):** Use se você ativou o ambiente virtual (`(.venv)` aparece no início da linha do seu terminal)
ou se usa o Python instalado globalmente. <br>
> **Opção 2 (`.\.venv\Scripts\python.exe`):** Use se o ambiente virtual **não** estiver ativado, chamando o
executável direto da pasta `.venv`.

## TESTES UNITÁRIOS

1) Instale as dependências do projeto uma vez:
```powershell
# Opção 1: Com o ambiente (.venv) ativado ou Python global
python -m pip install -r .\Back-end\requirements.txt

# Opção 2: Comando direto pelo executável da pasta (.venv), sem precisar ativar
.\.venv\Scripts\python.exe -m pip install -r .\Back-end\requirements.txt
```

2) Para rodar todos os testes unitários do back-end e do RAG:
```powershell
# Opção 1: 
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py

#Opção 2:
.\.venv\Scripts\python.exe .\Dados-RAG\RAG\testes-automatizados\executar_testes.py
```

**Atenção:** Os testes unitários não precisam do Ollama, de índice vetorial pronto ou de chave de API.

## AVALIAÇÃO DE RECUPERAÇÃO (MÉTRICAS OBJETIVAS, SEM JUIZ LLM)

Com o Ollama ativo e o índice atualizado, rode:
```powershell
# Opção 1:
python .\Dados-RAG\RAG\avaliar.py

# Opção 2:
.\.venv\Scripts\python.exe .\Dados-RAG\RAG\avaliar.py
```

O relatório mostra **acerto@1, acerto@4, MRR e abstenção em perguntas fora do escopo**.
Isso mede a busca, não a qualidade do texto. 

**Atenção:** Acerto@4 não garante que o primeiro resultado, usado como principal na resposta, seja o programa esperado.

## AVALIAÇÃO RAGAS OPCIONAL (JUIZ LOCAL, SEM API PAGA)

1) Instale as dependências extras:
```powershell
# Opção 1:
python -m pip install -r .\Dados-RAG\RAG\requirements-avaliacao.txt

# Opção 2:
.\.venv\Scripts\python.exe -m pip install -r .\Dados-RAG\RAG\requirements-avaliacao.txt
```

2) Garanta que o Ollama está em execução e baixe os modelos:
```powershell
ollama pull bge-m3
ollama pull qwen2.5:3b
```

3) Crie/atualize o índice vetorial se ainda não existir:
```powershell
# Opção 1:
python .\Dados-RAG\RAG\ingestao.py

# Opção 2:
.\.venv\Scripts\python.exe .\Dados-RAG\RAG\ingestao.py
```
4) Rode os testes unitários e uma amostra curta de avaliação:
```powershell
# Opção 1:
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas --limite 2

# Opção 2:
.\.venv\Scripts\python.exe .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas --limite 2
```

**Opcional:** Rodar avaliação RAGAS completa (sem limite)
```powershell
# Opção 1:
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas

# Opção 2:
.\.venv\Scripts\python.exe .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas
```

Para avaliar todos os casos, retire `--limite 2`. A execução pode demorar porque o juiz
local analisa cada resposta e contexto. Os arquivos `amostras.jsonl`, `resultados.jsonl`,
`resumo.json` e `metricas.csv` são gravados em `Dados-RAG\RAG\avaliacao`.

## SOBRE O RAGAS NO PROJETO
O RAGAS mede fidelidade, uso, precisão e recall dos contextos nas perguntas em escopo,
com um LLM juiz. Não tem finalidade de provar que o benefício existe, que a fonte está atualizada nem que uma pessoa tem direito. 

Saídas produzidas no terminal: 
Acerto@1, acerto@4, MRR, respostas com contexto em perguntas válidas e abstenções corretas fora do escopo são métricas objetivas complementares para acompanhar a busca.
O **juiz local `qwen2.5:3b`** errou ao avaliar uma recusa fora do escopo. Por isso, a aderência ao escopo é medida pelo campo objetivo `abstencao_correta`, não por uma nota RAGAS.

## OPÇÃO DE COMANDO ÚNICO PARA RODAR TUDO:

```powershell
Opção 1: Usando o Python 3.12 instalado no sistema (py -3.12)
py -3.12 -m pip install -r .\Back-end\requirements.txt; if ($?) { py -3.12 -m pip install -r .\Dados-RAG\RAG\requirements-avaliacao.txt }; if ($?) { ollama pull bge-m3 }; if ($?) { ollama pull qwen2.5:3b }; if ($?) { py -3.12 .\Dados-RAG\RAG\ingestao.py }; if ($?) { py -3.12 .\Dados-RAG\RAG\avaliar.py }; if ($?) { py -3.12 .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas --limite 2 }

Opção 2: Chamando direto pelo executável da pasta (.venv), sem precisar ativar
.\.venv\Scripts\python.exe -m pip install -r .\Back-end\requirements.txt; if ($?) { .\.venv\Scripts\python.exe -m pip install -r .\Dados-RAG\RAG\requirements-avaliacao.txt }; if ($?) { ollama pull bge-m3 }; if ($?) { ollama pull qwen2.5:3b }; if ($?) { .\.venv\Scripts\python.exe .\Dados-RAG\RAG\ingestao.py }; if ($?) { .\.venv\Scripts\python.exe .\Dados-RAG\RAG\avaliar.py }; if ($?) { .\.venv\Scripts\python.exe .\Dados-RAG\RAG\testes-automatizados\executar_testes.py --com-ragas --limite 2 }
```

### Ordem dos testes executados:
- **A.** Testes Unitários (Back-end e RAG); 
- **B.** Ingestão de Dados (Criação do Índice Vetorial); 
- **C.** Avaliação de Recuperação (Métricas Objetivas, sem juiz LLM): Aqui mede qualidade da busca **acerto@1, acerto@4, MRR e abstenções fora do escopo**; 
- **D.** Testes Unitários + Avaliação RAGAS (Juiz local, sem APIs pagas). 
