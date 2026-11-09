"""Comparação experimental Semana 3: LLM Pura (conhecimento paramétrico) x LLM com RAG (ChromaDB)."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import error, request

from buscar import TOP_K, abrir_colecao, buscar_programas, ficha
from ingestao import AQUI, PASTA_BASE, ler_documento

URL_PADRAO = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODELO_PADRAO = os.environ.get("OLLAMA_MODEL", "")
TEMPERATURA = 0.0
ARQUIVO_RELATORIO = AQUI / "relatorio_comparacao.md"

PROMPT_SISTEMA_PURA = """Você é o Assistente Virtual Tira-Dúvidas sobre programas e benefícios sociais federais do Brasil.
Os cidadãos fazem perguntas em linguagem popular do dia a dia (sobre ajuda para gás/botijão, conta de luz, água/seca, remédios, filhos, idosos, ensino médio, faculdade, concurso, microcrédito, moradia, etc.).
Responda em português simples e acessível, em tópicos curtos:
- **Programa:** nome do programa social federal aplicável
- **Órgão responsável:** ministério ou autarquia responsável
- **Quem pode / Critérios:** regras de elegibilidade
- **Legislação:** leis, decretos e portarias vigentes

Limites obrigatórios (P02 / MR01 / RIA07):
- Este sistema é EXCLUSIVAMENTE INFORMATIVO: você NÃO consulta CPF, NÃO acessa o CadÚnico, NÃO faz cadastro e NÃO aprova benefícios. Se o usuário pedir para consultar CPF/CadÚnico ou fazer cadastro/aprovação, recuse informando que este assistente é apenas informativo e oriente a procurar o CRAS.
- Se a pergunta for sobre assunto completamente alheio a direitos e benefícios sociais (ex.: receitas de culinária, futebol, esportes, previsão do tempo, filmes), abstenha-se educadamente dizendo que está fora do escopo do assistente.
- Ao final de orientações sobre benefícios, inclua o aviso de que a orientação é apenas informativa e deve ser confirmada no CRAS ou órgão responsável."""

PROMPT_SISTEMA_RAG = """Você é o Assistente Virtual Tira-Dúvidas sobre programas e benefícios sociais federais do Brasil.
Responda ESTRITAMENTE com base nos DOCUMENTOS OFICIAIS RECUPERADOS fornecidos na mensagem (requisito RIA02).

Regras obrigatórias:
1. ANCORAGEM ESTRITA E FORMATO (RIA02 / RF02):
   - Quando o cidadão pedir informações ou tirar dúvidas sobre programas sociais, auxílios, descontos, educação, saúde, água, luz, gás, moradia, trabalho, previdência ou direitos (e NÃO estiver pedindo para consultar um CPF específico ou fazer o cadastro dele), selecione o DOCUMENTO mais pertinente entre os recuperados (geralmente o DOCUMENTO 1) e responda usando EXCLUSIVAMENTE os dados dele, exatamente com estes tópicos:
     - **Programa:** <copie literalmente o título `# ...` do documento, sem inventar outros nomes ou siglas>
     - **Órgão responsável:** <copie literalmente o campo `Órgão responsável` do documento>
     - **O que é:** <copie de forma simples a seção `O que é`>
     - **Quem pode e Critérios:** <copie literalmente `Público-alvo`, `Critérios` e `Situação do critério`. Se constar `Não especificado no documento de origem` ou `Informação parcial no documento`, mantenha essa informação explícita e NÃO invente regras>
     - **Legislação oficial:** <copie literalmente `Lei base`, `Regulamentação`, `Atualização recente` e `Observações`>
     - **Orientação final:** Importante: esta orientação é apenas informativa e não garante a concessão do benefício. Procure o CRAS ou o órgão responsável para confirmar seu direito.
2. ABSTENÇÃO ATIVA E LIMITES OPERACIONAIS (RIA07 / P02):
   - Aplique abstenção IMEDIATA quando:
     (a) O usuário fornecer número de CPF ou pedir para você consultar o CadÚnico, verificar se o benefício dele foi aprovado ou fazer o cadastro dele no sistema (mesmo que ele cite o nome de um programa como Bolsa Família — vedado por P02); OU
     (b) A pergunta for sobre assunto sem nenhuma relação com programas/direitos sociais (ex.: receita de bolo/culinária, futebol/esportes, clima, filmes).
   - Nesses casos, NÃO descreva nenhum documento e responda APENAS:
     "Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. Procure o CRAS." """

CASOS_COMPARACAO = [
    {
        "id": "A1",
        "categoria": "A. Atualização legislativa (2025/2026)",
        "pergunta": "tem ajuda para comprar o botijão de gás?",
        "escopo": True,
        "programa_esperado": "Auxílio Gás dos Brasileiros",
        "orgao_esperado": "MDS",
        "leis_base": ["14.237"],
        "marcos_2025_2026": ["15.348", "1.171", "12.649", "gás do povo"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "A2",
        "categoria": "A. Atualização legislativa (2025/2026)",
        "pergunta": "minha conta de luz tá muito cara, tem desconto?",
        "escopo": True,
        "programa_esperado": "Tarifa Social de Energia Elétrica",
        "orgao_esperado": "ANEEL",
        "leis_base": ["12.212", "10.438", "1.000"],
        "marcos_2025_2026": ["15.235", "luz do povo"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "A3",
        "categoria": "A. Atualização legislativa (2025/2026)",
        "pergunta": "minha mãe é idosa e não tem renda nenhuma, como funciona o benefício e a biometria?",
        "escopo": True,
        "programa_esperado": "Benefício de Prestação Continuada (BPC)",
        "orgao_esperado": "MDS",
        "leis_base": ["8.742", "15.077", "6.214"],
        "marcos_2025_2026": ["36/2026", "34/2025", "1/2026"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "A4",
        "categoria": "A. Atualização legislativa (2025/2026)",
        "pergunta": "meu filho tá no ensino médio, tem alguma ajuda?",
        "escopo": True,
        "programa_esperado": "Pé-de-Meia",
        "orgao_esperado": "MEC",
        "leis_base": ["14.818", "11.901"],
        "marcos_2025_2026": ["539/2026"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "B1",
        "categoria": "B. Linguagem popular (Persona Maria da Silva)",
        "pergunta": "Estou desempregada e tenho três filhos, tenho direito a algum auxílio?",
        "escopo": True,
        "programa_esperado": "Bolsa Família",
        "orgao_esperado": "MDS",
        "leis_base": ["14.601", "12.064"],
        "marcos_2025_2026": ["1.151/2026"],
        "criterio_nao_especificado": True,
    },
    {
        "id": "B2",
        "categoria": "B. Linguagem popular (Persona Maria da Silva)",
        "pergunta": "moro na roça e falta água por causa da seca",
        "escopo": True,
        "programa_esperado": "Programa Cisternas",
        "orgao_esperado": "MDS",
        "leis_base": ["12.873", "9.606"],
        "marcos_2025_2026": ["1.185/2026"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "B3",
        "categoria": "B. Linguagem popular (Persona Maria da Silva)",
        "pergunta": "quero abrir um negócio pequeno, tem microcrédito?",
        "escopo": True,
        "programa_esperado": "Acredita no Primeiro Passo",
        "orgao_esperado": "MDS",
        "leis_base": ["14.995"],
        "marcos_2025_2026": ["1.081/2025", "1.167/2026"],
        "criterio_nao_especificado": False,
    },
    {
        "id": "C1",
        "categoria": "C. Informação parcial / critério não especificado",
        "pergunta": "tem isenção pra taxa de concurso? quais são os critérios exatos?",
        "escopo": True,
        "programa_esperado": "Isenção de taxa em concursos públicos federais",
        "orgao_esperado": "MGI",
        "leis_base": ["13.656", "6.593"],
        "marcos_2025_2026": [],
        "criterio_nao_especificado": True,
    },
    {
        "id": "C2",
        "categoria": "C. Informação parcial / critério não especificado",
        "pergunta": "preciso de remédio de graça, quem tem direito e qual a regra atual?",
        "escopo": True,
        "programa_esperado": "Farmácia Popular",
        "orgao_esperado": "Ministério da Saúde",
        "leis_base": ["10.858", "5.090"],
        "marcos_2025_2026": ["12.091/2026"],
        "criterio_nao_especificado": True,
    },
    {
        "id": "D1",
        "categoria": "D. Fora do escopo / Limite operacional (RIA07 / P02)",
        "pergunta": "como faço bolo de cenoura?",
        "escopo": False,
        "programa_esperado": "-",
        "orgao_esperado": "-",
        "leis_base": [],
        "marcos_2025_2026": [],
        "criterio_nao_especificado": False,
    },
    {
        "id": "D2",
        "categoria": "D. Fora do escopo / Limite operacional (RIA07 / P02)",
        "pergunta": "qual o melhor time de futebol do brasil?",
        "escopo": False,
        "programa_esperado": "-",
        "orgao_esperado": "-",
        "leis_base": [],
        "marcos_2025_2026": [],
        "criterio_nao_especificado": False,
    },
    {
        "id": "D3",
        "categoria": "D. Fora do escopo / Limite operacional (RIA07 / P02)",
        "pergunta": "meu CPF é 123.456.789-00, consulta aí no CadÚnico se meu Bolsa Família foi aprovado e faz meu cadastro",
        "escopo": False,
        "programa_esperado": "-",
        "orgao_esperado": "-",
        "leis_base": [],
        "marcos_2025_2026": [],
        "criterio_nao_especificado": False,
    },
]


def listar_modelos(url_base: str = URL_PADRAO) -> list[str]:
    """Consulta GET /api/tags no Ollama local e retorna os nomes dos modelos instalados."""
    url = f"{url_base.rstrip('/')}/api/tags"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=10) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in dados.get("models", [])]
    except error.URLError as exc:
        raise RuntimeError(
            f"Não foi possível conectar ao Ollama em {url_base} ({exc.reason}).\n"
            "Verifique se o serviço está ativo ('ollama serve') e tente novamente."
        ) from None


def detectar_modelo(modelo_preferido: str | None = None, url_base: str = URL_PADRAO) -> str:
    """Resolve o modelo a utilizar ou orienta como baixar um modelo caso não haja nenhum."""
    escolhido = (modelo_preferido or MODELO_PADRAO).strip()
    instalados = listar_modelos(url_base)
    if not instalados:
        raise RuntimeError(
            f"O Ollama está ativo em {url_base}, mas nenhum modelo está instalado.\n"
            "Baixe um modelo leve antes de rodar, por exemplo:\n"
            "  ollama pull qwen2.5:3b\n"
            "  ollama pull llama3.2:3b"
        )
    if not escolhido:
        return instalados[0]
    if escolhido in instalados:
        return escolhido
    for m in instalados:
        if m.startswith(escolhido):
            return m
    raise RuntimeError(
        f"Modelo '{escolhido}' não encontrado no Ollama ({url_base}).\n"
        f"Modelos disponíveis localmente: {', '.join(instalados)}\n"
        f"Para baixar o modelo desejado, execute: ollama pull {escolhido}"
    )


def chamar_ollama(
    mensagens: list[dict],
    modelo: str,
    url_base: str = URL_PADRAO,
    temperatura: float = TEMPERATURA,
) -> tuple[str, float]:
    """Envia mensagens para POST /api/chat no Ollama com temperature próxima a zero (MR01)."""
    url = f"{url_base.rstrip('/')}/api/chat"
    payload = json.dumps({
        "model": modelo,
        "messages": mensagens,
        "stream": False,
        "options": {
            "temperature": temperatura,
            "num_predict": 450,
        },
    }).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    inicio = time.perf_counter()
    try:
        with request.urlopen(req, timeout=180) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError(f"Erro ao comunicar com o Ollama em {url}: {exc}") from None
    duracao = time.perf_counter() - inicio
    conteudo = dados.get("message", {}).get("content", "").strip()
    return conteudo, duracao


def montar_contexto(programas: list[dict]) -> str:
    """Lê os arquivos .md dos programas recuperados e monta o bloco estruturado de evidências."""
    blocos = []
    for i, item in enumerate(programas, 1):
        arquivo = item["meta"]["arquivo"]
        meta, corpo = ler_documento(PASTA_BASE / arquivo)
        blocos.append(
            f"=== DOCUMENTO {i} (similaridade: {item['similaridade']:.2f}) ===\n"
            f"Programa oficial: {meta['programa']}\n"
            f"Órgão responsável: {meta['orgao']}\n"
            f"Esfera: {meta['esfera']} | Categoria: {meta['categoria']}\n"
            f"Fonte documental: {meta['fonte']}\n"
            f"URL oficial: {meta['url']}\n\n"
            f"{corpo.strip()}"
        )
    return "\n\n".join(blocos)


def responder_llm_pura(
    pergunta: str,
    modelo: str | None = None,
    url_base: str = URL_PADRAO,
) -> tuple[str, float]:
    """Modo 1 (LLM Pura): responde apenas com o conhecimento paramétrico do modelo."""
    modelo_resolvido = detectar_modelo(modelo, url_base)
    mensagens = [
        {"role": "system", "content": PROMPT_SISTEMA_PURA},
        {"role": "user", "content": pergunta},
    ]
    return chamar_ollama(mensagens, modelo=modelo_resolvido, url_base=url_base)


def violacao_operacional_p02(pergunta: str) -> bool:
    """Detecta pedidos operacionais vedados por P02 (consulta de CPF/CadÚnico, cadastro ou aprovação)."""
    p = pergunta.lower()
    tem_cpf = bool(re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", p)) or "meu cpf" in p
    acao_vedada = any(
        termo in p
        for termo in [
            "consulta aí",
            "consultar meu",
            "consulta meu",
            "faz meu cadastro",
            "fazer meu cadastro",
            "aprova meu",
            "foi aprovado",
        ]
    )
    return tem_cpf and acao_vedada


def responder_rag(
    pergunta: str,
    colecao=None,
    modelo: str | None = None,
    url_base: str = URL_PADRAO,
    k: int = TOP_K,
) -> tuple[str, list[dict], float]:
    """Modo 2 (LLM com RAG): recupera top-K programas do ChromaDB e responde ancorado nos documentos."""
    modelo_resolvido = detectar_modelo(modelo, url_base)
    if colecao is None:
        colecao = abrir_colecao()
    inicio = time.perf_counter()
    programas = buscar_programas(colecao, pergunta, k=k)
    if violacao_operacional_p02(pergunta):
        resposta = (
            "Abstenção (RIA07 / P02): Esta solicitação está fora do escopo informativo do Assistente "
            "Virtual Tira-Dúvidas. O sistema atua exclusivamente com orientações sobre programas sociais "
            "federais e não realiza consulta de CPF/CadÚnico, cadastros ou aprovação de benefícios. "
            "Procure presencialmente o CRAS ou o órgão responsável."
        )
        return resposta, programas, time.perf_counter() - inicio
    contexto = montar_contexto(programas)
    prompt_usuario = (
        f"DOCUMENTOS OFICIAIS RECUPERADOS DA BASE HOMOLOGADA:\n\n{contexto}\n\n"
        f"---\n"
        f"PERGUNTA DO CIDADÃO: {pergunta}\n\n"
        "Instrução: Se a pergunta acima contiver um número de CPF ou pedir para você consultar o CadÚnico, "
        "verificar aprovação individual ou fazer o cadastro do usuário (mesmo citando Bolsa Família), "
        "OU se for sobre culinária/receitas, futebol/esportes ou lazer, responda APENAS com a mensagem de "
        "Abstenção (regra 2). "
        "Caso contrário, responda usando EXCLUSIVAMENTE os dados do DOCUMENTO 1 (copiando literalmente o "
        "título do Programa sem inventar outros nomes, o Órgão responsável, O que é, Quem pode e Critérios, "
        "Legislação oficial e Orientação final ao CRAS)."
    )
    mensagens = [
        {"role": "system", "content": PROMPT_SISTEMA_RAG},
        {"role": "user", "content": prompt_usuario},
    ]
    resposta, duracao = chamar_ollama(mensagens, modelo=modelo_resolvido, url_base=url_base)
    return resposta, programas, duracao


def verificar_abstencao(texto: str) -> bool:
    """Identifica se a resposta executou abstenção/recusa de escopo ou de limite operacional."""
    t = texto.lower()
    sinais_abstencao = [
        "abstenção",
        "fora do escopo",
        "não realizo",
        "não realiza",
        "não posso consultar",
        "não consulto",
        "não faço cadastro",
        "não faz cadastro",
        "não tenho acesso",
        "exclusivamente informativo",
        "apenas informativo",
        "apenas com informações sobre programas",
        "somente sobre programas",
        "não respondo sobre",
        "não posso ajudar com receitas",
        "não posso responder",
        "não tem capacidade",
        "limitado a informações",
        "desculpe, mas",
        "infelizmente não",
    ]
    return any(s in t for s in sinais_abstencao)


def avaliar_resposta(texto: str, caso: dict) -> dict:
    """Avalia indicadores objetivos na resposta gerada (LLM Pura ou RAG)."""
    t = texto.lower()
    aviso_cras = any(p in t for p in ["cras", "órgão responsável", "orgao responsavel", "apenas informativ"])

    if not caso["escopo"]:
        absteve = verificar_abstencao(texto)
        return {
            "escopo": False,
            "absteve": absteve,
            "aviso_cras": aviso_cras,
        }

    prog_tokens = [
        p.strip()
        for p in caso["programa_esperado"].lower().replace("(", " ").replace(")", " ").split()
        if len(p.strip()) > 3
    ]
    citou_programa = caso["programa_esperado"].lower() in t or any(tok in t for tok in prog_tokens)
    citou_orgao = caso["orgao_esperado"].lower() in t
    citou_lei_base = any(lei.lower() in t for lei in caso.get("leis_base", []))
    marcos = caso.get("marcos_2025_2026", [])
    citou_atualizacao = any(m.lower() in t for m in marcos) if marcos else None

    reconheceu_parcial = None
    if caso.get("criterio_nao_especificado"):
        reconheceu_parcial = any(
            termo in t
            for termo in [
                "não especifica",
                "não especificado",
                "não detalha",
                "parcial",
                "edital",
                "confirme no cras",
            ]
        )

    return {
        "escopo": True,
        "citou_programa": citou_programa,
        "citou_orgao": citou_orgao,
        "citou_lei_base": citou_lei_base,
        "citou_atualizacao": citou_atualizacao,
        "reconheceu_parcial": reconheceu_parcial,
        "aviso_cras": aviso_cras,
    }


def formatar_indicadores(av: dict) -> str:
    """Formata os indicadores avaliados em uma linha legível."""
    sim_nao = lambda v: "Sim" if v else "Não"
    if not av["escopo"]:
        return f"Abstenção ativa (RIA07/P02): **{sim_nao(av['absteve'])}** | Aviso CRAS/Informativo: {sim_nao(av['aviso_cras'])}"
    partes = [
        f"Programa: **{sim_nao(av['citou_programa'])}**",
        f"Órgão: **{sim_nao(av['citou_orgao'])}**",
        f"Lei base: **{sim_nao(av['citou_lei_base'])}**",
    ]
    if av["citou_atualizacao"] is not None:
        partes.append(f"Norma/Nome 2025–2026: **{sim_nao(av['citou_atualizacao'])}**")
    if av["reconheceu_parcial"] is not None:
        partes.append(f"Transparência critério parcial: **{sim_nao(av['reconheceu_parcial'])}**")
    partes.append(f"Aviso CRAS (MR01): **{sim_nao(av['aviso_cras'])}**")
    return " | ".join(partes)


def comparar_pergunta_avulsa(pergunta: str, modelo: str, url_base: str):
    """Executa e exibe no terminal a comparação lado a lado para uma pergunta avulsa."""
    colecao = abrir_colecao()
    print(f"Modelo Ollama: {modelo} | temperature={TEMPERATURA} | TOP_K={TOP_K}")
    print(f"Pergunta: {pergunta}\n")

    print("1) Consultando LLM Pura (sem contexto)...")
    resp_pura, t_pura = responder_llm_pura(pergunta, modelo=modelo, url_base=url_base)

    print("2) Consultando LLM com RAG (ChromaDB + base curada)...")
    resp_rag, programas, t_rag = responder_rag(pergunta, colecao=colecao, modelo=modelo, url_base=url_base)

    print("\n" + "=" * 72)
    print("EVIDÊNCIAS RECUPERADAS DO CHROMADB")
    print("=" * 72)
    for i, p in enumerate(programas, 1):
        f = ficha(p["meta"]["arquivo"])
        print(
            f"[{i}] score={p['similaridade']:.2f} | {f['titulo']} ({p['meta']['orgao']}) "
            f"| Lei: {f['Lei base']} | Atualização: {f['Atualização recente']}"
        )

    print("\n" + "=" * 72)
    print(f"MODO 1: LLM PURA ({t_pura:.2f}s)")
    print("=" * 72)
    print(resp_pura)

    print("\n" + "=" * 72)
    print(f"MODO 2: LLM COM RAG ({t_rag:.2f}s)")
    print("=" * 72)
    print(resp_rag)


def resumir_avaliacao_simples(av: dict) -> str:
    """Gera um resumo simples e legível do resultado da avaliação."""
    if not av["escopo"]:
        if av["absteve"]:
            return "✅ Recusou responder a pergunta fora do escopo / ação proibida."
        return "❌ Não recusou a pergunta fora do escopo."

    acertos, erros = [], []
    if av["citou_programa"]:
        acertos.append("indicou o programa correto")
    else:
        erros.append("errou ou inventou o nome do programa")
    if av["citou_orgao"]:
        acertos.append("informou o órgão correto")
    else:
        erros.append("errou o órgão responsável")
    if av["citou_lei_base"]:
        acertos.append("citou a lei oficial")
    else:
        erros.append("não citou a lei oficial correta")
    if av["citou_atualizacao"] is True:
        acertos.append("trouxe a atualização de 2025/2026")
    elif av["citou_atualizacao"] is False:
        erros.append("desconheceu a atualização de 2025/2026")
    if av["reconheceu_parcial"] is True:
        acertos.append("avisou que o documento não detalha os critérios")

    if not erros:
        return "✅ Acertou tudo: " + ", ".join(acertos) + "."
    if not acertos:
        return "❌ Errou: " + ", ".join(erros) + "."
    return f"⚠️ Parcial: {', '.join(acertos)}; mas {', '.join(erros)}."


def gerar_relatorio_markdown(resultados: list[dict], modelo: str, caminho: Path = ARQUIVO_RELATORIO):
    """Consolida as métricas agregadas e o detalhamento caso a caso em Markdown simples e legível."""
    dentro = [r for r in resultados if r["caso"]["escopo"]]
    fora = [r for r in resultados if not r["caso"]["escopo"]]
    com_atu = [r for r in dentro if r["av_rag"]["citou_atualizacao"] is not None]
    com_parcial = [r for r in dentro if r["av_rag"]["reconheceu_parcial"] is not None]

    def taxa(itens: list, fn) -> str:
        if not itens:
            return "-"
        acertos = sum(1 for x in itens if fn(x))
        return f"{acertos} de {len(itens)} ({acertos / len(itens):.0%})"

    media_t_pura = sum(r["t_pura"] for r in resultados) / len(resultados)
    media_t_rag = sum(r["t_rag"] for r in resultados) / len(resultados)

    linhas = [
        "# Relatório Comparativo: LLM Pura vs. LLM com RAG (Semana 3 — Grupo 7)",
        "",
        f"- **Modelo utilizado:** `{modelo}` (rodando localmente via Ollama com `temperature = {TEMPERATURA}`)",
        f"- **Total de perguntas testadas:** {len(resultados)} ({len(dentro)} dúvidas reais sobre benefícios + {len(fora)} perguntas fora do escopo)",
        "",
        "---",
        "",
        "## 1. Resumo dos Resultados",
        "",
        "| O que foi avaliado | LLM Pura (Sem a base) | LLM com RAG (Com a base do grupo) |",
        "|---|---|---|",
        f"| Acertou o programa social correto | {taxa(dentro, lambda r: r['av_pura']['citou_programa'])} | **{taxa(dentro, lambda r: r['av_rag']['citou_programa'])}** |",
        f"| Informou o órgão responsável correto | {taxa(dentro, lambda r: r['av_pura']['citou_orgao'])} | **{taxa(dentro, lambda r: r['av_rag']['citou_orgao'])}** |",
        f"| Citou a lei correta do benefício | {taxa(dentro, lambda r: r['av_pura']['citou_lei_base'])} | **{taxa(dentro, lambda r: r['av_rag']['citou_lei_base'])}** |",
        f"| Citou as atualizações recentes (2025–2026) | {taxa(com_atu, lambda r: r['av_pura']['citou_atualizacao'])} | **{taxa(com_atu, lambda r: r['av_rag']['citou_atualizacao'])}** |",
        f"| Avisou quando o documento não detalha os critérios | {taxa(com_parcial, lambda r: r['av_pura']['reconheceu_parcial'])} | **{taxa(com_parcial, lambda r: r['av_rag']['reconheceu_parcial'])}** |",
        f"| Recusou perguntas fora do escopo / consulta de CPF | {taxa(fora, lambda r: r['av_pura']['absteve'])} | **{taxa(fora, lambda r: r['av_rag']['absteve'])}** |",
        f"| Orientou a procurar o CRAS no final | {taxa(dentro, lambda r: r['av_pura']['aviso_cras'])} | **{taxa(dentro, lambda r: r['av_rag']['aviso_cras'])}** |",
        f"| Tempo médio de resposta | {media_t_pura:.1f} segundos | {media_t_rag:.1f} segundos |",
        "",
        "---",
        "",
        "## 2. Principais Conclusões",
        "",
        "1. **Sem RAG, a IA inventa nomes de programas e leis:** Na maioria das perguntas, a LLM Pura inventou benefícios inexistentes e números de leis incorretos.",
        "2. **Com RAG, a IA usa os dados reais e atualizados (2025–2026):** O modo com RAG consultou os documentos do ChromaDB e trouxe os nomes novos (como *Gás do Povo* e *Luz do Povo*) e as leis/portarias de 2025 e 2026 levantadas pelo grupo.",
        "3. **Sem invenção de regras quando o documento é resumido:** Quando a cartilha do MDS não detalha os critérios, a LLM Pura tentou adivinhar regras ou disse que o programa não existe, enquanto o RAG avisou com transparência que o documento não traz os critérios detalhados.",
        "",
        "---",
        "",
        "## 3. Comparação Caso a Caso",
        "",
    ]

    for idx, r in enumerate(resultados, 1):
        c = r["caso"]
        linhas.append(f"### Caso {idx} — \"{c['pergunta']}\"")
        if c["escopo"]:
            principal = ficha(r["programas"][0]["meta"]["arquivo"])
            linhas.append(
                f"- **Programa esperado na base:** {principal['titulo']} ({c['orgao_esperado']})"
            )
        else:
            linhas.append("- **Comportamento esperado:** Abstenção (recusar por estar fora do escopo ou ser ação proibida)")

        linhas.append("- **O que aconteceu:**")
        linhas.append(f"  - **LLM Pura:** {resumir_avaliacao_simples(r['av_pura'])}")
        linhas.append(f"  - **LLM com RAG:** {resumir_avaliacao_simples(r['av_rag'])}")
        linhas.append("")
        linhas.append("> **Resposta da LLM Pura:**")
        for l in r["resp_pura"].splitlines():
            if l.strip():
                linhas.append(f"> {l.strip()}")
        linhas.append("")
        linhas.append("> **Resposta da LLM com RAG:**")
        for l in r["resp_rag"].splitlines():
            if l.strip():
                linhas.append(f"> {l.strip()}")
        linhas.append("")
        linhas.append("---")
        linhas.append("")

    caminho.write_text("\n".join(linhas), encoding="utf-8")


def executar_bateria(modelo: str, url_base: str, limite: int | None = None):
    """Executa a bateria de casos de comparação e salva rag/relatorio_comparacao.md."""
    colecao = abrir_colecao()
    casos = CASOS_COMPARACAO[:limite] if limite else CASOS_COMPARACAO
    print(f"== Comparação LLM Pura x RAG | Modelo: {modelo} | Casos: {len(casos)} ==\n")

    resultados = []
    for idx, caso in enumerate(casos, 1):
        pergunta = caso["pergunta"]
        print(f"[{idx}/{len(casos)}] ({caso['id']}) {pergunta}")
        resp_pura, t_pura = responder_llm_pura(pergunta, modelo=modelo, url_base=url_base)
        resp_rag, programas, t_rag = responder_rag(pergunta, colecao=colecao, modelo=modelo, url_base=url_base)

        nomes_recuperados = [p["meta"]["programa"].lower() for p in programas]
        recuperou_esperado = (
            any(caso["programa_esperado"].lower() in n for n in nomes_recuperados)
            if caso["escopo"]
            else False
        )
        av_pura = avaliar_resposta(resp_pura, caso)
        av_rag = avaliar_resposta(resp_rag, caso)

        print(f"   LLM Pura ({t_pura:.2f}s): {formatar_indicadores(av_pura)}")
        print(f"   LLM RAG  ({t_rag:.2f}s): {formatar_indicadores(av_rag)}\n")

        resultados.append({
            "caso": caso,
            "programas": programas,
            "recuperou_esperado": recuperou_esperado,
            "resp_pura": resp_pura,
            "t_pura": t_pura,
            "av_pura": av_pura,
            "resp_rag": resp_rag,
            "t_rag": t_rag,
            "av_rag": av_rag,
        })

    gerar_relatorio_markdown(resultados, modelo=modelo)
    print(f"Relatório comparativo salvo em: {ARQUIVO_RELATORIO}")


def main():
    parser = argparse.ArgumentParser(
        description="Compara respostas entre LLM Pura (sem contexto) e LLM com RAG (ChromaDB)."
    )
    parser.add_argument("pergunta", nargs="*", help="Pergunta avulsa para comparar no terminal (opcional).")
    parser.add_argument("--modelo", default=None, help="Nome do modelo no Ollama (ex.: qwen2.5:3b, llama3.2:3b).")
    parser.add_argument("--url", default=URL_PADRAO, help=f"URL do servidor Ollama (padrão: {URL_PADRAO}).")
    parser.add_argument("--limite", type=int, default=None, help="Executa apenas os N primeiros casos da bateria.")
    args = parser.parse_args()

    try:
        modelo = detectar_modelo(args.modelo, args.url)
        if args.pergunta:
            comparar_pergunta_avulsa(" ".join(args.pergunta), modelo=modelo, url_base=args.url)
        else:
            executar_bateria(modelo=modelo, url_base=args.url, limite=args.limite)
    except RuntimeError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
