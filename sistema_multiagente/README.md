> Integração local: o chat agora chama `POST /api/orientar`, que executa este grafo.
> Veja [a ligação HTTP e seus limites](../Back-end/INTEGRACAO.md).
> Testes do pacote: `python -m unittest sistema_multiagente.test_guardrail_ajuda`.
> CLI: `python -m sistema_multiagente.main "sua pergunta"`.

# Sistema Multiagente — Assistente Socioassistencial (LangGraph + Gemini + RAG)

Assistente virtual **exclusivamente informativo** sobre programas e benefícios sociais federais do Brasil, implementado com arquitetura multiagente em **LangGraph**, modelos **Google Gemini** escalonados por complexidade cognitiva e recuperação documental (**RAG**) ancorada nos **42 programas oficiais** catalogados em `Dados-RAG/programas_sociais_legislacao_links_oficiais.csv`.

> **Importante (Premissa P02):** este sistema **não realiza cadastro**, **não consulta CPF nem o CadÚnico**, **não verifica aprovação individual** e **não substitui** o atendimento presencial do CRAS, CREAS ou do órgão gestor.

---

## Sumário

1. [Arquitetura e Padrões de Execução](#arquitetura-e-padrões-de-execução)
2. [Acolhimento de Segurança e Resposta Dupla](#acolhimento-de-segurança-e-resposta-dupla)
3. [Tiers de Modelos Gemini](#tiers-de-modelos-gemini)
4. [Estrutura de Arquivos](#estrutura-de-arquivos)
5. [Como Executar do Zero](#como-executar-do-zero)
6. [Exemplos de Execução no CLI](#exemplos-de-execução-no-cli)
7. [Uso Programático em Python](#uso-programático-em-python)
8. [Testes Automatizados](#testes-automatizados)
9. [Privacidade (LGPD) e Solução de Problemas](#privacidade-lgpd-e-solução-de-problemas)

---

## Arquitetura e Padrões de Execução

O grafo LangGraph inicia sempre no nó **`guardrail`**, que valida o escopo socioassistencial, detecta sinais que exijam mensagem adicional de apoio/proteção e escolhe dinamicamente o padrão de execução mais adequado ao relato do cidadão:

```mermaid
flowchart TD
    START(["START"]) --> G["guardrail (escopo + segurança + seletor de padrão)"]
    G --> ROT{"dentro_do_escopo == True?"}
    ROT -- "Não (fora de escopo, P02 ou crise/fraude isolada)" --> END1(["END"])
    ROT -- "Sim: padrao ou reflexion" --> EXT["extrator_perfil -> retriever -> analista_elegibilidade -> comunicador"]
    ROT -- "Sim: rewoo" --> REW["rewoo_planner -> rewoo_worker (ChromaDB) -> rewoo_solver"]
    EXT --> REFL{"padrao == reflexion?"}
    REFL -- "Sim" --> CRIT["reflexion_critico <-> reflexion_revisor (até 2 revisões)"]
    REFL -- "Não" --> CONS["consolidar_encaminhamento_ajuda"]
    CRIT --> CONS
    REW --> CONS
    CONS --> END2(["END"])
```

### Os 3 padrões agênticos

- **`padrao`** *(relatos simples ou dúvida direta sobre um único tema)*:
  `extrator_perfil` → `retriever` (ChromaDB) → `analista_elegibilidade` (ancoragem estrita RIA02) → `comunicador` (linguagem simples + próximos passos práticos + aviso P02).
- **`rewoo`** *(Reasoning Without Observation — relatos multifacetados com 3+ vulnerabilidades ou perguntas amplas/comparativas)*:
  `rewoo_planner` (extrai perfil e decompõe em subconsultas `#E1..#En`) → `rewoo_worker` (executa as buscas em lote no ChromaDB sem chamar LLM) → `rewoo_solver` (analisa todas as evidências consolidadas e redige a orientação integrada).
- **`reflexion`** *(casos limítrofes, acumulação de benefícios como BPC + Bolsa Família ou exigência explícita de detalhamento legal/normativo 2024–2026)*:
  Executa o pipeline base seguido de auditoria crítica (`reflexion_critico` ↔ `reflexion_revisor`, até `MAX_ITERACOES_REFLEXION = 2`) para verificar ancoragem documental (RIA02), nomes oficiais, leis/portarias e ausência de alucinações.

---

## Acolhimento de Segurança e Resposta Dupla

O nó `guardrail` combina **regras determinísticas de alta precisão**, **classificação estruturada via LLM** e **fallback contra filtros `SAFETY`** para tratar situações sensíveis sem aplicar bloqueio punitivo:

| Situação identificada | Comportamento do pipeline | `status_api` |
| --- | --- | --- |
| **Vulnerabilidade/dúvida de benefício + Autoextermínio e/ou Código Penal** *(ex.: mãe solo desempregada expressando ideação suicida ou vítima de violência doméstica buscando auxílio)* | Executa integralmente o fluxo de benefícios (`padrao`/`rewoo`/`reflexion`) **e** anexa a mensagem adicional de apoio/proteção com canais oficiais | `sucesso_com_encaminhamento_ajuda` |
| **Autoextermínio ou matéria penal isolada (sem contexto socioeconômico) ou pedido explícito de fraude/ilícito** | Encerra no `guardrail` sem acionar busca de benefícios nem apoiar ilícitos, exibindo os canais oficiais de ajuda/proteção | `encaminhamento_ajuda` |
| **Relato socioeconômico legítimo** *(inclusive metáforas coloquiais como "a conta de luz está me matando" ou "cortaram meu Bolsa Família")* | Executa normalmente o padrão selecionado (`mensagem_apoio = None`) | `sucesso` |
| **Assunto fora de escopo** *(receitas, futebol)* ou **operação proibida P02 pura** *(consultar CPF/CadÚnico)* | Encerra no `guardrail` com orientação institucional padrão | `bloqueado_guardrail` |
| **Falha técnica da API Gemini** | Comportamento *fail-closed* (preservando a mensagem de apoio caso um sinal crítico já tenha sido identificado) | `erro_api` |

**Canais públicos oficiais indicados na mensagem adicional de apoio:**
- **Autoextermínio / autolesão:** CVV (**Ligue 188** e `https://cvv.org.br`, 24h gratuito e sigiloso), SAMU (**192**), Corpo de Bombeiros (**193**), CAPS / UPA 24h / UBS pelo **SUS** e **CRAS / CREAS**.
- **Elementos do Código Penal (violência, ameaça, abuso, crimes ou ilícitos):** Polícia Militar (**190**), Polícia Civil / Delegacia (**197**), Central de Atendimento à Mulher (**Ligue 180**), Disque Direitos Humanos (**Disque 100**), Disque-Denúncia (**181**), **CREAS / CRAS** e Defensoria Pública (**Ligue 129**).

---

## Tiers de Modelos Gemini

Definidos centralmente em [`config.py`](config.py) com temperatura `0.0` e fallback automático entre modelos verificados:

| Tier | Modelo Principal | Fallbacks | Agentes atendidos |
| --- | --- | --- | --- |
| `rapido` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite`, `gemini-4-hydrogen` | `guardrail`, `extrator_perfil` |
| `equilibrado` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite`, `gemini-4-hydrogen` | `comunicador`, `rewoo_planner`, `rewoo_comunicador`, `reflexion_revisor` |
| `analitico` | `gemini-4-hydrogen` | `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` | `analista_elegibilidade`, `rewoo_solver`, `reflexion_critico` |

---

## Estrutura de Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| [`main.py`](main.py) | Ponto de entrada CLI (execução direta, modo interativo, flag `--debug` e exibição separada de benefícios + mensagem adicional de apoio). |
| [`graph.py`](graph.py) | Construção e compilação do `StateGraph` no LangGraph, roteadores condicionais, `estado_inicial()` e `executar_fluxo()`. |
| [`agents.py`](agents.py) | Prompts e implementação de todos os agentes (`guardrail`, `extrator_perfil`, `retriever`, `analista_elegibilidade`, `comunicador`, `rewoo_*`, `reflexion_*` e `consolidar_encaminhamento_ajuda`). |
| [`schemas.py`](schemas.py) | `EstadoSistema`, constantes de `status_api` e modelos Pydantic de saída estruturada (`ValidacaoEscopo`, `PerfilSocioeconomico`, `AnaliseElegibilidade`, `PlanoReWOO`, `AvaliacaoCriticaReflexion`). |
| [`rag.py`](rag.py) | Integração com a base oficial em `Dados-RAG/` (ChromaDB local automático ou `KnowledgeBase` com Ollama), busca em lote ReWOO e detectores determinísticos (P02, segurança, metáforas e contexto socioeconômico). |
| [`config.py`](config.py) | Carregamento de `GOOGLE_API_KEY`, cache de clientes `ChatGoogleGenerativeAI`, escalonamento por tiers e fallback automático (`invocar_estruturado` / `invocar_texto`). |
| [`test_guardrail_ajuda.py`](test_guardrail_ajuda.py) | Suíte de testes unitários em `unittest` (sem chamadas reais de rede). |
| `.env` *(não versionado)* | Arquivo local contendo `GOOGLE_API_KEY` (ignorado pelo `.gitignore`). |

---

## Como Executar do Zero

### 1. Pré-requisitos

- **Python 3.12 ou superior** instalado;
- **Git** instalado;
- Uma chave válida da API do Google Gemini (**`GOOGLE_API_KEY`**), obtida no [Google AI Studio](https://aistudio.google.com/apikey).
- *(Opcional)* **Ollama** com o modelo `bge-m3` e índice `Dados-RAG` já ingerido. **Não é obrigatório:** se o Ollama ou o índice externo não estiverem disponíveis, o módulo `rag.py` cria e indexa automaticamente uma coleção local do ChromaDB em `rag/chroma_db/` usando o CSV oficial de `Dados-RAG/` logo na primeira consulta.

### 2. Clonar o repositório

```bash
git clone https://github.com/purpleaither/SegundoChallenge.git
cd SegundoChallenge
```

*(Todos os comandos abaixo assumem que você está na **raiz do repositório** `SegundoChallenge/`.)*

### 3. Criar e ativar o ambiente virtual (`.venv`)

**macOS / Linux (zsh/bash):**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar as dependências

Com o ambiente virtual ativo:

```bash
python -m pip install --upgrade pip
python -m pip install langgraph langchain-core langchain-google-genai pydantic python-dotenv chromadb
```

### 5. Configurar a variável `GOOGLE_API_KEY`

Crie o arquivo `sistema_multiagente/.env` (este arquivo já está listado no `.gitignore` e nunca deve ser commitado):

**macOS / Linux:**

```bash
cat <<'EOF' > sistema_multiagente/.env
GOOGLE_API_KEY=COLE_SUA_CHAVE_GEMINI_AQUI
EOF
```

**Windows (PowerShell):**

```powershell
Set-Content -Path .\sistema_multiagente\.env -Value "GOOGLE_API_KEY=COLE_SUA_CHAVE_GEMINI_AQUI"
```

*(Alternativamente, você também pode exportar `GOOGLE_API_KEY` diretamente como variável de ambiente no terminal.)*

### 6. Executar o sistema

**Execução passando a pergunta diretamente (macOS / Linux):**

```bash
./.venv/bin/python sistema_multiagente/main.py "Estou desempregada, tenho 3 filhos pequenos e não consigo pagar a conta de luz"
```

**Execução passando a pergunta diretamente (Windows PowerShell):**

```powershell
.\.venv\Scripts\python.exe .\sistema_multiagente\main.py "Estou desempregada, tenho 3 filhos pequenos e não consigo pagar a conta de luz"
```

**Modo interativo (o programa pede a frase no terminal):**

```bash
./.venv/bin/python sistema_multiagente/main.py
```

**Modo `--debug` (recomendado para inspeção técnica):**
Exibe o padrão escolhido, modelos escalados por agente, perfil extraído, programas recuperados do ChromaDB com score de similaridade, parecer de elegibilidade e auditorias do Reflexion:

```bash
./.venv/bin/python sistema_multiagente/main.py --debug "Estou desempregada e tenho 3 filhos pequenos, quais auxílios posso pedir?"
```

> **Primeira execução:** ao consultar a base vetorial local pela primeira vez sem Ollama, o ChromaDB pode baixar o modelo de embedding padrão localmente e indexar os 42 programas oficiais em `rag/chroma_db/`. A partir da segunda execução, a busca é imediata.

---

## Exemplos de Execução no CLI

Abaixo estão exemplos práticos para testar cada caminho do grafo com `--debug`:

1. **Padrão `padrao` (dúvida direta / relato simples):**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "A conta de luz está me matando, ganho pouco e moro sozinha. Tenho direito a desconto?"
   ```

2. **Padrão `rewoo` (relato multifacetado com 3+ frentes):**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "Moro na roça sem água por causa da seca, tenho 2 filhos no ensino médio, minha mãe idosa sem renda mora comigo e o botijão de gás está muito caro"
   ```

3. **Padrão `reflexion` (acumulação de benefícios / exigência normativa):**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "Posso acumular BPC com Bolsa Família? Quais leis e portarias de 2024 a 2026 tratam disso?"
   ```

4. **Resposta dupla — vulnerabilidade + autoextermínio (exibe Benefícios + Mensagem Adicional de Apoio):**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "sou mae solteira tenho 3 filhos, desempregada, nao aguento mais quero morrer"
   ```

5. **Resposta dupla — vulnerabilidade + Código Penal (exibe Benefícios + Canais de Proteção):**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "Meu marido me bate, saí de casa com meus 2 filhos desempregada e sem renda, quais benefícios posso pedir?"
   ```

6. **Bloqueio operacional P02 (consulta de CPF) e fora de escopo:**
   ```bash
   ./.venv/bin/python sistema_multiagente/main.py --debug "Meu CPF é 123.456.789-00, consulta aí no CadÚnico se meu Bolsa Família foi aprovado"
   ./.venv/bin/python sistema_multiagente/main.py --debug "Me passa uma receita de bolo de cenoura"
   ```

---

## Uso Programático em Python

Se quiser integrar o pipeline diretamente em outro script ou API Python:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("sistema_multiagente").resolve()))
from sistema_multiagente.graph import executar_fluxo

estado = executar_fluxo("Estou desempregada e tenho 2 filhos pequenos, quais auxílios existem?")

print("Status:", estado["status_api"])
print("Padrão:", estado["padrao_execucao"])
print("Resposta consolidada:\n", estado["resposta_final"])

# Em casos de resposta dupla (benefícios + apoio), também é possível acessar separadamente:
if estado["resposta_beneficios"] and estado["mensagem_apoio"]:
    print("Benefícios:", estado["resposta_beneficios"])
    print("Apoio oficial:", estado["mensagem_apoio"])
```

---

## Testes Automatizados

Os testes unitários do `sistema_multiagente` usam `unittest.mock` e **não consomem créditos da API Gemini nem precisam de acesso à internet**.

**Executar a suíte do sistema multiagente (macOS / Linux):**

```bash
./.venv/bin/python -m unittest discover -s sistema_multiagente -p "test_*.py" -v
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s sistema_multiagente -p "test_*.py" -v
```

**Executar também os testes unitários da base `Dados-RAG`:**

```bash
./.venv/bin/python -m unittest discover -s Dados-RAG/RAG/testes-automatizados -p "test_*.py" -v
```

---

## Privacidade (LGPD) e Solução de Problemas

### Privacidade (RNF05)
- O pipeline é **stateless**: mensagens e relatos sensíveis do cidadão são mantidos **apenas em memória RAM** durante a execução da requisição e **nunca são gravados em disco, bancos de dados ou arquivos de log**.
- Nunca compartilhe CPF ou documentos pessoais nas consultas.

### Problemas Comuns

- **`ValueError: Erro: GOOGLE_API_KEY não encontrada no arquivo .env`**
  Verifique se o arquivo `sistema_multiagente/.env` existe e contém `GOOGLE_API_KEY=...` sem espaços extras ao redor do `=`.
- **`Status da API: erro_api` (ex.: `ConnectError`, `429 RESOURCE_EXHAUSTED`, `503 UNAVAILABLE`)**
  Confirme acesso à internet e validade/cota da chave Gemini no Google AI Studio. O módulo `config.py` tenta automaticamente os modelos de fallback antes de retornar o erro *fail-closed*.
- **`ModuleNotFoundError` ao rodar `main.py`**
  Certifique-se de executar com o Python do ambiente virtual (`./.venv/bin/python` ou `.\.venv\Scripts\python.exe`) após instalar as dependências do [Passo 4](#4-instalar-as-dependências).
- **Ollama não instalado ou parado**
  Não impede a execução: `rag.py` detecta `ModelUnavailableError` e alterna automaticamente para a coleção local em `rag/chroma_db/`.
