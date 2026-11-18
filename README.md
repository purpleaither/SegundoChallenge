-AINDA NÃO FINALIZADO-
# 🏡 Assistente virtual de benefícios sociais 🏡

## Descrição do projeto ✏️

Chatbot institucional que ajuda na busca de programas sociais potencialmente relacionados à situação do usuário. A resposta é informativa, usa trechos recuperados da base e cita fontes, mas não decide elegibilidade.

## Arquitetura adotada (RAG x LLM) 🏗️

O relatório [Documentos/semana3-resumo.md](Documentos/semana3-resumo.md) registra a decisão da Semana 03: usar a configuração T5 — embeddings multilíngues `bge-m3` pelo Ollama, busca vetorial ChromaDB, limiar de similaridade e resposta determinística. Isso elimina chamadas pagas e evita que um modelo reescreva ou invente leis e critérios.

O limiar padrão é `RAG_MIN_SIMILARITY=0.532`, valor experimental do relatório. Como a base atual também inclui textos legislativos, esse valor precisa ser recalibrado em um conjunto de perguntas independente antes de qualquer uso institucional.

## Organização dos arquivos 🧱

COMPLEMENTAR COM OUTROS CAMINHOS
- `Back-end/`: API FastAPI e testes do servidor.
- `Front-end/`: Arquivos da interface aberta no navegador, contém: HTML que define o conteúdo, CSS estilização da página e JavaScript comportamento.
- `Front-end/app.js`: Tela principal do chat, responsável por enviar perguntas à API, atualizar a conversa e apresentar respostas e fontes. O sufixo .js identifica os arquivos JavaSript.
`Dados/`: Dados usados pela aplicação, incluindo o CSV dos programas e os módulos Python do RAG. No Windows, o índice vetorial fica por padrão fora do repositório em %LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2.
- `Dados-RAG/programas_sociais_legislacao_links_oficiais.csv`: base estruturada dos 42 programas.
- `Dados-RAG/RAG/`: preparação dos dados, ingestão, recuperação, respostas determinísticas, avaliação RAGAS e testes.
- `Dados-RAG/RAG/base/`: fichas Markdown derivadas do CSV.
- `Dados-RAG/RAG/fontes/`: textos legislativos oficiais baixados.
- `Dados-RAG/testes-automatizados/`: Testes unitários e script executar_testes.py, também inicia a bateria RAGAS integrada.
- `Dados-RAG/avaliacao/`: Casos versionados do teste integrado RAG + RAGAS, os resultados locais são gerados ao executar a avaliação.
- `Dados-RAG/__init__.py`: Arquivo Python que identifica Dados como pacote e contém uma breve descrição. Em algumas versões do Python, os diretórios podem ser importados sem ele, mas matemos para deixar explicito a estrutura do pacote e é convencional.
- `COMO_RODAR.txt`: Comandos no terminal para instalar dependências, iniciar o Ollama, testar respostas, roda testes automáticos e avaliar com RAGAS.
- `__pycache__/`: Pasta criada automaticamente pelo Python para guardar bytecode compilado (.pyc) e acelerar importações futuras. 
- `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v2`: Banco vetorial persistente do ChromaDB no Windows. É derivado dos dados e recriável com script de ingestão.
- `Documentos/`: Relatórios e documentos do projeto.

## Instalação e execução no Windows 💻

1. Pré-requisitos: 
- Python 3.12.

2. Preparação do ambiente
Crie um ambiente com Python 3.12 e instale as dependências da API:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Back-end\requirements.txt
ollama pull bge-m3
```

Baixe fontes novas, se necessário, e gere/recrie o índice vetorial:

```powershell
python .\Dados-RAG\RAG\baixar_fontes.py
python .\Dados-RAG\RAG\ingestao.py
```

Inicie a API:

```powershell
python -m uvicorn main:app --reload --app-dir .\Back-end
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`. No Windows, o índice persistente fica por padrão em `%LOCALAPPDATA%\AssistenteVirtualDF\vetor-v3`; configure `VECTOR_DB_PATH` para outro local, se necessário. Depois da atualização para o conjunto v3, execute a ingestão novamente antes de consultar a API.

## Sistema multiagentes 👷

## Testes 🧩

Com as dependências instaladas, um comando executa os testes unitários do back-end e do RAG, sem Ollama, chave de API ou chamadas pagas:

```powershell
python .\Dados-RAG\RAG\testes-automatizados\executar_testes.py
```

O passo a passo está em [Dados-RAG/RAG/testes-automatizados/COMO_EXECUTAR.txt](Dados-RAG/RAG/testes-automatizados/COMO_EXECUTAR.txt).

## Limitações conhecidas 🚧

## Colaboradores ♟️

<table>
  <tr>
    <td align="center" valign="top">
      <a href="https://github.com/anagiulias">
        <img src="https://github.com/anagiulias.png?size=120" width="100" />
      </a>
      <br />
      <strong>GIULIO SANTOS</strong>
      <br />
      <a href="https://github.com/anagiulias">@Giulio</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/IanLucca12">
        <img src="https://github.com/IanLucca12.png?size=120" width="100" />
      </a>
      <br />
      <strong>IAN MESQUITA</strong>
      <br />
      <a href="https://github.com/IanLucca12">@IanLucca12</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/idelmondez">
        <img src="https://github.com/idelmondez.png?size=120" width="100" />
      </a>
      <br />
      <strong>IVAN OLIVEIRA</strong>
      <br />
      <a href="https://github.com/idelmondez">@idelmondez</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/volktz">
        <img src="https://github.com/volktz.png?size=120" width="100" />
      </a>
      <br />
      <strong>PAULO SILVA</strong>
      <br />
      <a href="https://github.com/volktz">@volktz</a>
    </td>
    <td align="center" valign="top">
      <a href="https://github.com/purpleaither">
        <img src="https://github.com/purpleaither.png?size=120" width="100" />
      </a>
      <br />
      <strong>THAYNA DUTRA</strong>
      <br />
      <a href="https://github.com/purpleaither">@purpleaither</a>
    </td>
  </tr>
</table>
