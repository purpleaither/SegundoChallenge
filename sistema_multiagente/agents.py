"""Agentes (nós do LangGraph) do assistente socioassistencial nos padrões Padrão, ReWOO e Reflexion.

Cada nó recebe o EstadoSistema e devolve apenas os campos que atualiza. Falhas de API são
convertidas em status_api="erro_api" + resposta_final explicativa (fail-closed).
"""

import json
from pathlib import Path
import sys

from dotenv import load_dotenv

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))
load_dotenv(PASTA_ATUAL / ".env")

from config import invocar_estruturado, invocar_texto
from rag import executar_buscas_rewoo, recuperar_documentos_com_perfil, violacao_operacional_p02
from schemas import (
    AnaliseElegibilidade,
    AvaliacaoCriticaReflexion,
    EstadoSistema,
    PerfilSocioeconomico,
    PlanoReWOO,
    ValidacaoEscopo,
)

STATUS_ERRO_API = "erro_api"
STATUS_BLOQUEADO = "bloqueado_guardrail"
STATUS_EM_PROCESSAMENTO = "em_processamento"
STATUS_SUCESSO = "sucesso"

MAX_ITERACOES_REFLEXION = 2

AVISO_INSTITUCIONAL = (
    "Importante: esta orientação é apenas informativa e não garante a concessão do benefício. "
    "A confirmação do seu direito e a concessão são feitas pelo CRAS ou pelo órgão responsável."
)

MENSAGEM_FORA_DE_ESCOPO = (
    "Desculpe, mas não posso ajudar com esse assunto. Sou um assistente exclusivamente informativo sobre "
    "programas, benefícios e direitos socioassistenciais (como Bolsa Família, BPC, Tarifa Social, Farmácia "
    "Popular, entre outros). Se você quiser, conte um pouco da sua situação (trabalho, renda, família, "
    "moradia, saúde) e eu indico quais programas podem ajudar."
)

MENSAGEM_OPERACAO_PROIBIDA = (
    "Desculpe, mas não posso realizar esse pedido. Este assistente é exclusivamente informativo: ele não "
    "consulta CPF nem o Cadastro Único (CadÚnico), não verifica se um benefício foi aprovado e não faz "
    "cadastros. Para isso, procure o CRAS (Centro de Referência de Assistência Social) mais próximo da sua "
    "casa, levando documento com foto e CPF. Por favor, não compartilhe seus dados pessoais neste chat. "
    "Se quiser, posso explicar como funcionam os programas sociais e quem tem direito a eles."
)


def _erro_api(agente: str, erro: Exception) -> dict:
    """Converte uma falha de chamada ao LLM/RAG em atualização de estado fail-closed."""
    return {
        "status_api": STATUS_ERRO_API,
        "motivo_rejeicao": f"Falha no agente '{agente}': {type(erro).__name__}: {str(erro)[:200]}",
        "resposta_final": (
            "Desculpe, não consegui concluir a sua orientação agora por uma falha técnica no serviço de "
            "inteligência artificial. Tente novamente em alguns minutos. Se precisar de ajuda imediata, "
            "procure o CRAS mais próximo da sua casa."
        ),
    }


def _registrar_modelo(state: EstadoSistema, agente: str, modelo: str) -> dict[str, str]:
    """Retorna cópia atualizada do dicionário de modelos utilizados pelos nós executados."""
    atuais = dict(state.get("modelos_utilizados") or {})
    atuais[agente] = modelo
    return atuais


def _garantir_aviso_institucional(texto: str) -> str:
    """Garante a presença literal do aviso institucional obrigatório (P02)."""
    texto_limpo = texto.strip()
    if AVISO_INSTITUCIONAL not in texto_limpo:
        return f"{texto_limpo}\n\n{AVISO_INSTITUCIONAL}"
    return texto_limpo


# ---------------------------------------------------------------------------
# Blocos normativos reutilizados entre Padrão, ReWOO e Reflexion (sem duplicar regras)
# ---------------------------------------------------------------------------
REGRAS_EXTRACAO_PERFIL = """Regras de extração de perfil (RIA01):
- Registre APENAS fatos declarados ou diretamente implícitos no relato. NÃO invente renda, idade, número de filhos, inscrição no CadÚnico ou qualquer dado não informado.
- Quando um dado não for informado, use null (campos de texto) ou lista vazia (campos de lista).
- Mapeie a fala popular para termos técnicos/oficiais (RIA01). Exemplos:
  - "tô sem emprego" -> situacao_trabalho="desempregado"
  - "3 meninos pequenos" -> composicao_familiar=["3 filhos/crianças"]
  - "moro na roça" -> condicoes_especificas=["zona rural"]
  - "falta água por causa da seca" -> condicoes_especificas=["falta de água/seca"]
  - "botijão caro" -> condicoes_especificas=["gás de cozinha caro"]
  - "minha mãe idosa" -> composicao_familiar=["idosa na família"]
- Em palavras_chave_busca, combine termos oficiais e populares úteis para buscar programas sociais (ex.: "Bolsa Família", "transferência de renda", "baixa renda", "crianças", "cisternas", "Tarifa Social", "BPC", "pessoa idosa").
- resumo_situacao: uma ou duas frases objetivas, em português."""

REGRAS_ANALISE_RIA02 = """Ancoragem estrita (RIA02) — regras obrigatórias de elegibilidade:
1. Analise EXCLUSIVAMENTE os programas presentes nos documentos oficiais fornecidos. Avalie os programas recuperados pertinentes e NÃO acrescente nenhum outro programa externo.
2. Para cada programa, compare a seção "## Público e critérios" (Público-alvo, Critérios, Status dos critérios no documento) e a seção "## Legislação" (Legislação base, Regulamentação principal, Atualização normativa recente, Observações) com os dados do cidadão.
3. Classifique status_elegibilidade:
   - "elegivel": o perfil declarado atende a todos os requisitos explícitos do documento.
   - "potencialmente_elegivel": o programa tem relação com a necessidade e parte dos requisitos bate, mas algo precisa ser comprovado ou confirmado (ex.: renda, inscrição no CadÚnico, regra de acumulação não detalhada).
   - "criterio_nao_especificado_na_base": o programa tem relação com a necessidade, mas o documento traz "Não especificado no documento de origem" ou "Informação parcial no documento" nos critérios.
   - "inelegivel": o programa não tem relação com a necessidade do cidadão ou há impedimento claro escrito no documento.
4. NUNCA invente limites de renda, idades, valores, prazos, regras de acumulação ou normas que não estejam escritos no documento. Se o documento não detalha (inclusive sobre acumulação entre benefícios), registre essa lacuna literalmente em observacoes_documentais e oriente confirmação no CRAS/órgão responsável.
5. Copie LITERALMENTE: nome_programa (título "# ..." do documento), orgao_responsavel (campo "Órgão responsável") e base_legal (Legislação base; Regulamentação principal; Atualização normativa recente — mantenha as normas de 2024–2026 citadas).
6. criterios_atendidos: somente requisitos do documento que os dados do cidadão já satisfazem. criterios_pendentes_ou_impeditivos: o que precisa ser comprovado/confirmado ou impede o acesso.
7. resumo_parecer: parecer técnico curto, em português, destacando os programas mais pertinentes e as lacunas da base."""

REGRAS_COMUNICACAO_P02 = f"""Regras obrigatórias de comunicação ao cidadão (linguagem simples + P02):
1. Tom de voz: acolhedor, empático, respeitoso, claro e direto. Frases curtas, sem jargão burocrático. Trate a pessoa por "você".
2. Use APENAS os programas e informações ancorados nos DOCUMENTOS OFICIAIS fornecidos (RIA02). Não invente programas, valores, limites de renda, prazos, regras de acumulação ou leis.
3. Apresente apenas os programas com status "elegivel", "potencialmente_elegivel" ou "criterio_nao_especificado_na_base". Não apresente os "inelegivel".
4. Para cada programa apresentado, traduza o "juridiquês" para o que ele significa na prática, mantendo explicitamente: o nome oficial do programa, o órgão responsável e a legislação citada no documento (lei base, regulamentação e atualização recente de 2024–2026, quando houver).
5. Transparência: quando um critério (ou regra específica como acumulação de benefícios) constar como não especificado ou parcial no documento oficial, diga com clareza que a base resumida não traz esse detalhe e que a confirmação deve ser feita presencialmente no CRAS ou órgão responsável.
6. Se nenhum programa for pertinente, diga isso com honestidade e oriente a procurar o CRAS para uma avaliação completa.
7. Inclua obrigatoriamente uma seção intitulada "**Próximos passos práticos**", numerada, com ações concretas (ex.: ir ao CRAS/órgão responsável, verificar/atualizar CadÚnico, levar documento com foto, CPF, comprovante de residência e renda).
8. Termine SEMPRE com este aviso, literalmente: "{AVISO_INSTITUCIONAL}"
9. Responda em português, em Markdown simples (títulos curtos, listas)."""


# ---------------------------------------------------------------------------
# Agente 1 — Guardrail + Seletor de Padrão de Execução (RIA07 / P02)
# ---------------------------------------------------------------------------
PROMPT_GUARDRAIL = """Você é o Guardrail e Seletor de Arquitetura de um assistente público, exclusivamente informativo, sobre programas e benefícios sociais federais do Brasil.
Você tem duas responsabilidades conjuntas: (A) validar o escopo da mensagem e (B) selecionar o padrão ideal de execução quando a mensagem for válida.

PARTE A — Validação de Escopo (RIA07 / P02):
Marque eh_valido=True (tipo_bloqueio=None) quando a mensagem:
- relatar situação socioeconômica, familiar, de vulnerabilidade, saúde, deficiência, moradia, educação, trabalho/desemprego/renda, alimentação, água/luz/gás ou vida na zona rural; OU
- trouxer dúvidas informativas sobre programas, benefícios, auxílios, descontos, isenções, leis/portarias ou direitos sociais (como funcionam, quem pode, pode acumular, qual a lei, onde pedir).
A linguagem popular e informal ("tô sem emprego", "moro na roça", "botijão") é perfeitamente válida.

Marque eh_valido=False (e deixe padrao_execucao=None, justificativa_padrao=None) quando:
1. tipo_bloqueio="fora_de_escopo": assunto alheio a direitos ou benefícios sociais (ex.: receitas de culinária, futebol/esportes, piadas, programação, previsão do tempo, filmes, curiosidades gerais).
2. tipo_bloqueio="operacao_proibida_cpf_cadastro": pedido de OPERAÇÃO vedada: consultar CPF ou CadÚnico, verificar se o benefício individual foi aprovado/está ativo, fazer/atualizar cadastro pelo chat ou conceder benefício (mesmo que cite programa social). Perguntas apenas informativas ("como me inscrevo no CadÚnico?") são VÁLIDAS.

PARTE B — Seleção do Padrão de Execução (SOMENTE quando eh_valido=True):
Escolha exatamente um valor para padrao_execucao e explique em justificativa_padrao (uma frase curta):
1. "padrao":
   - Dúvidas diretas sobre um único benefício ou tema específico (ex.: ensino médio/Pé-de-Meia, conta de luz, auxílio gás, remédio gratuito); OU
   - Relatos socioeconômicos simples e lineares com poucas variáveis (ex.: desempregada com filhos pedindo orientação básica).
2. "rewoo":
   - Relatos multifacetados combinando 3 ou mais vulnerabilidades/necessidades distintas no mesmo pedido (ex.: moradia na roça/zona rural + seca/falta de água + filhos na escola + idoso/pessoa com deficiência + conta de luz/gás/moradia); OU
   - Perguntas amplas/comparativas que exigem decompor a busca em várias frentes independentes no banco de programas antes de consolidar a orientação.
3. "reflexion":
   - Casos limítrofes, ambíguos ou com potenciais conflitos de regras e acumulação de benefícios (ex.: acumular BPC com Bolsa Família, renda no limite, vínculo formal parcial/MEI x benefício); OU
   - Pedidos com exigência explícita de detalhamento legal/normativo (citação exata de leis, decretos, portarias de 2024–2026, regras de biometria, critérios exatos ou lacunas normativas) onde uma auditoria crítica de ancoragem documental (RIA02) evita alucinação.

Escreva motivo e justificativa_padrao de forma objetiva, em português."""


def agente_guardrail(state: EstadoSistema) -> dict:
    mensagem = state["mensagem_usuario"]
    try:
        if violacao_operacional_p02(mensagem):
            validacao = ValidacaoEscopo(
                eh_valido=False,
                motivo="Pedido de consulta de CPF/CadÚnico, aprovação ou cadastro (vedado por P02).",
                tipo_bloqueio="operacao_proibida_cpf_cadastro",
                padrao_execucao=None,
                justificativa_padrao=None,
            )
            modelos = _registrar_modelo(state, "guardrail", "regra_deterministica_p02")
        else:
            validacao, modelo_usado = invocar_estruturado(
                "guardrail", ValidacaoEscopo, PROMPT_GUARDRAIL, f"Mensagem do cidadão:\n{mensagem}"
            )
            modelos = _registrar_modelo(state, "guardrail", modelo_usado)
    except Exception as erro:  # fail-closed
        return {
            "dentro_do_escopo": False,
            "padrao_execucao": None,
            "justificativa_padrao": None,
            **_erro_api("guardrail", erro),
        }

    if validacao.eh_valido:
        padrao = validacao.padrao_execucao or "padrao"
        justificativa = validacao.justificativa_padrao or validacao.motivo
        return {
            "dentro_do_escopo": True,
            "motivo_rejeicao": None,
            "padrao_execucao": padrao,
            "justificativa_padrao": justificativa,
            "modelos_utilizados": modelos,
            "status_api": STATUS_EM_PROCESSAMENTO,
        }

    proibida = validacao.tipo_bloqueio == "operacao_proibida_cpf_cadastro"
    return {
        "dentro_do_escopo": False,
        "motivo_rejeicao": validacao.motivo,
        "padrao_execucao": None,
        "justificativa_padrao": None,
        "modelos_utilizados": modelos,
        "status_api": STATUS_BLOQUEADO,
        "resposta_final": MENSAGEM_OPERACAO_PROIBIDA if proibida else MENSAGEM_FORA_DE_ESCOPO,
    }


# ---------------------------------------------------------------------------
# Caminho Padrão (e Base do Reflexion): Extrator -> Retriever -> Analista -> Comunicador
# ---------------------------------------------------------------------------
PROMPT_EXTRATOR = f"""Você é um assistente social técnico que lê o relato livre de um cidadão e extrai seu perfil socioeconômico estruturado.

{REGRAS_EXTRACAO_PERFIL}"""


def agente_extrator_perfil(state: EstadoSistema) -> dict:
    try:
        perfil, modelo_usado = invocar_estruturado(
            "extrator_perfil",
            PerfilSocioeconomico,
            PROMPT_EXTRATOR,
            f"Relato do cidadão:\n{state['mensagem_usuario']}",
        )
    except Exception as erro:
        return _erro_api("extrator_perfil", erro)
    return {
        "perfil_extraido": perfil.model_dump(),
        "modelos_utilizados": _registrar_modelo(state, "extrator_perfil", modelo_usado),
    }


def agente_retriever(state: EstadoSistema) -> dict:
    try:
        resultado = recuperar_documentos_com_perfil(state["mensagem_usuario"], state.get("perfil_extraido"))
    except Exception as erro:
        return _erro_api("retriever", erro)
    return {
        "query_busca": resultado["query_busca"],
        "documentos_encontrados": resultado["documentos"],
        "modelos_utilizados": _registrar_modelo(state, "retriever", "chromadb_local"),
    }


PROMPT_ANALISTA = f"""Você é um Analista de Elegibilidade de programas sociais federais. Você cruza os critérios legais dos DOCUMENTOS OFICIAIS RECUPERADOS com o perfil do cidadão.

{REGRAS_ANALISE_RIA02}"""


def agente_analista_elegibilidade(state: EstadoSistema) -> dict:
    documentos = state.get("documentos_encontrados") or []
    if not documentos:
        analise = AnaliseElegibilidade(
            programas_avaliados=[],
            resumo_parecer="Nenhum documento suficientemente relevante foi recuperado da base oficial para esta situação.",
        )
        return {
            "analise_elegibilidade": analise.model_dump(),
            "modelos_utilizados": _registrar_modelo(state, "analista_elegibilidade", "sem_documentos"),
        }

    prompt_usuario = (
        "DOCUMENTOS OFICIAIS RECUPERADOS DA BASE HOMOLOGADA:\n\n"
        + "\n\n".join(documentos)
        + "\n\n---\nPERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + f"\n\nRELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}"
    )
    try:
        analise, modelo_usado = invocar_estruturado(
            "analista_elegibilidade", AnaliseElegibilidade, PROMPT_ANALISTA, prompt_usuario
        )
    except Exception as erro:
        return _erro_api("analista_elegibilidade", erro)
    return {
        "analise_elegibilidade": analise.model_dump(),
        "modelos_utilizados": _registrar_modelo(state, "analista_elegibilidade", modelo_usado),
    }


PROMPT_COMUNICADOR = f"""Você é o Comunicador do Assistente Virtual Tira-Dúvidas sobre programas sociais federais. Você fala diretamente com cidadãos em situação de vulnerabilidade.

{REGRAS_COMUNICACAO_P02}"""


def agente_comunicador(state: EstadoSistema) -> dict:
    prompt_usuario = (
        f"MENSAGEM DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + "\n\nPARECER DO ANALISTA DE ELEGIBILIDADE:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
    )
    try:
        texto, modelo_usado = invocar_texto("comunicador", PROMPT_COMUNICADOR, prompt_usuario)
    except Exception as erro:
        return _erro_api("comunicador", erro)

    return {
        "resposta_final": _garantir_aviso_institucional(texto),
        "modelos_utilizados": _registrar_modelo(state, "comunicador", modelo_usado),
        "status_api": STATUS_SUCESSO,
    }


# ---------------------------------------------------------------------------
# Padrão ReWOO (Reasoning Without Observation): Planner -> Worker -> Solver
# ---------------------------------------------------------------------------
PROMPT_REWOO_PLANNER = f"""Você é o Planejador ReWOO (Reasoning Without Observation) de um assistente socioassistencial federal.
Em uma única etapa, você deve:
1. Extrair o perfil socioeconômico estruturado do cidadão sem inventar fatos.
2. Decompor o relato multifacetado ou dúvida comparativa em 2 a 5 passos independentes de busca de evidências (#E1, #E2, #E3...), onde cada passo investiga uma vulnerabilidade, público ou benefício distinto no banco vetorial ChromaDB.

{REGRAS_EXTRACAO_PERFIL}

Regras do Plano de Evidências ReWOO:
- Use identificadores sequenciais exatos: "#E1", "#E2", "#E3"...
- Cada passo deve focar em uma necessidade específica (ex.: #E1 acesso à água/seca rural; #E2 transferência de renda/filhos/educação; #E3 pessoa idosa sem renda/BPC; #E4 descontos em conta de luz e botijão de gás).
- Em query_busca, escreva termos semânticos ricos combinando fala popular e nomes técnicos/programas oficiais para maximizar a precisão da busca vetorial.
- Deixe categoria=null e esfera=null a menos que tenha certeza absoluta do filtro."""


def agente_rewoo_planner(state: EstadoSistema) -> dict:
    try:
        plano, modelo_usado = invocar_estruturado(
            "rewoo_planner",
            PlanoReWOO,
            PROMPT_REWOO_PLANNER,
            f"Relato multifacetado / dúvida do cidadão:\n{state['mensagem_usuario']}",
        )
    except Exception as erro:
        return _erro_api("rewoo_planner", erro)

    passos_dump = [p.model_dump() for p in plano.passos]
    return {
        "perfil_extraido": plano.perfil.model_dump(),
        "plano_rewoo": passos_dump,
        "modelos_utilizados": _registrar_modelo(state, "rewoo_planner", modelo_usado),
    }


def agente_rewoo_worker(state: EstadoSistema) -> dict:
    try:
        resultado = executar_buscas_rewoo(
            mensagem_usuario=state["mensagem_usuario"],
            perfil_extraido=state.get("perfil_extraido"),
            passos=state.get("plano_rewoo") or [],
        )
    except Exception as erro:
        return _erro_api("rewoo_worker", erro)

    return {
        "query_busca": resultado["query_busca"],
        "evidencias_rewoo": resultado["evidencias_rewoo"],
        "documentos_encontrados": resultado["documentos"],
        "modelos_utilizados": _registrar_modelo(state, "rewoo_worker", "chromadb_batch_worker"),
    }


PROMPT_REWOO_SOLVER_ANALISE = f"""Você é o Solver Analítico ReWOO do assistente socioassistencial federal.
Você recebe o relato multifacetado do cidadão, o perfil extraído, o mapa de subconsultas (#E1, #E2...) e o catálogo consolidado de documentos oficiais recuperados.
Avalie tecnicamente a elegibilidade do cidadão frente aos documentos recuperados cobrindo todas as frentes do plano (#E1..#En).

{REGRAS_ANALISE_RIA02}"""


def _formatar_evidencias_rewoo(passos: list[dict], evidencias: dict[str, list[str]]) -> str:
    blocos = []
    for idx, passo in enumerate(passos, 1):
        id_ev = passo.get("id_evidencia") or f"#E{idx}"
        foco = passo.get("foco_necessidade", "")
        query = passo.get("query_busca", "")
        docs = evidencias.get(id_ev) or []
        titulos = []
        for d in docs:
            prog = next((l.split(": ", 1)[1] for l in d.splitlines() if l.startswith("Programa oficial: ")), None)
            if prog:
                titulos.append(prog)
        resumo_ev = ", ".join(titulos) if titulos else "Nenhum documento específico acima do limiar neste passo."
        blocos.append(f"- {id_ev} | Foco: {foco} | Query: '{query}' -> Programas recuperados: {resumo_ev}")
    return "\n".join(blocos)


def agente_rewoo_solver(state: EstadoSistema) -> dict:
    documentos = state.get("documentos_encontrados") or []
    if not documentos:
        analise_vazia = AnaliseElegibilidade(
            programas_avaliados=[],
            resumo_parecer="Nenhum documento relevante foi encontrado na base oficial para as subconsultas planejadas.",
        )
        resposta_vazia = _garantir_aviso_institucional(
            "Não encontrei programas específicos na nossa base documental para atender com segurança a todos os "
            "pontos do seu relato.\n\n**Próximos passos práticos**\n"
            "1. Procure o CRAS (Centro de Referência de Assistência Social) mais próximo da sua residência.\n"
            "2. Leve documento de identificação com foto e CPF de todos os moradores da casa para avaliação no CadÚnico."
        )
        return {
            "analise_elegibilidade": analise_vazia.model_dump(),
            "resposta_final": resposta_vazia,
            "modelos_utilizados": _registrar_modelo(state, "rewoo_solver", "sem_documentos"),
            "status_api": STATUS_SUCESSO,
        }

    mapa_plano = _formatar_evidencias_rewoo(
        state.get("plano_rewoo") or [],
        state.get("evidencias_rewoo") or {},
    )
    prompt_analise = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + f"\n\nMAPA DO PLANO ReWOO (#E1..#En):\n{mapa_plano}\n\n"
        "DOCUMENTOS OFICIAIS CONSOLIDADOS (ÚNICA FONTE DE VERDADE — RIA02):\n\n"
        + "\n\n".join(documentos)
    )
    try:
        analise, modelo_analise = invocar_estruturado(
            "rewoo_solver", AnaliseElegibilidade, PROMPT_REWOO_SOLVER_ANALISE, prompt_analise
        )
        analise_dump = analise.model_dump()
        prompt_sintese = (
            f"MENSAGEM DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
            f"MAPA DAS NECESSIDADES INVESTIGADAS (ReWOO):\n{mapa_plano}\n\n"
            "PERFIL EXTRAÍDO:\n"
            + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
            + "\n\nPARECER DO SOLVER DE ELEGIBILIDADE:\n"
            + json.dumps(analise_dump, ensure_ascii=False, indent=2)
            + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
            + "\n\n".join(documentos)
        )
        texto_sintese, modelo_sintese = invocar_texto("comunicador", PROMPT_COMUNICADOR, prompt_sintese)
    except Exception as erro:
        return _erro_api("rewoo_solver", erro)

    modelos = _registrar_modelo(state, "rewoo_solver", modelo_analise)
    modelos["rewoo_comunicador"] = modelo_sintese
    return {
        "analise_elegibilidade": analise_dump,
        "resposta_final": _garantir_aviso_institucional(texto_sintese),
        "modelos_utilizados": modelos,
        "status_api": STATUS_SUCESSO,
    }


# ---------------------------------------------------------------------------
# Padrão Reflexion (Self-Reflection / Actor-Critic): Crítico <-> Revisor
# ---------------------------------------------------------------------------
PROMPT_REFLEXION_CRITICO = f"""Você é o Auditor Crítico (Reflexion) de conformidade normativa e documental de um assistente público socioassistencial.
Sua função é auditar rigorosamente o PARECER DE ELEGIBILIDADE e a RESPOSTA AO CIDADÃO confrontando-os com os DOCUMENTOS OFICIAIS RECUPERADOS e o RELATO DO CIDADÃO.

Verifique os 4 critérios obrigatórios:
1. Ancoragem Estrita (RIA02): A resposta ou análise inventou valores em reais, limites exatos de renda, idades, prazos, regras de acumulação de benefícios ou programas que NÃO estão escritos literalmente nos DOCUMENTOS OFICIAIS RECUPERADOS? (Se o cidadão perguntar se pode acumular dois benefícios e o documento não trouxer essa regra explícita, o assistente NÃO pode afirmar certeza sem base documental — deve explicar o que consta em cada documento e informar que a regra de acumulação não está detalhada na ficha resumida, orientando confirmação no CRAS/INSS).
2. Fidelidade Nominal e Legal: Todos os programas apresentados citam corretamente o nome oficial, o órgão responsável e a legislação presente no documento (Lei base, Regulamentação e normas/portarias de 2024–2026 constantes na ficha)?
3. Completude e Transparência: Algum programa claramente pertinente presente nos documentos recuperados foi omitido sem justificativa, ou deixou-se de avisar quando um critério consta como "Não especificado no documento de origem" / "Informação parcial no documento"?
4. Acessibilidade e Limites P02: O texto está em linguagem clara/acolhedora, contém a seção "**Próximos passos práticos**" e termina literalmente com o aviso: "{AVISO_INSTITUCIONAL}"?

Se TODOS os 4 itens estiverem plenamente atendidos sem alucinações nem omissões relevantes, marque aprovado=True (problemas_encontrados=[], instrucoes_correcao="").
Caso haja qualquer falha, marque aprovado=False, liste cada falha objetivamente em problemas_encontrados e escreva instrucoes_correcao diretas para o Revisor corrigir."""


def agente_reflexion_critico(state: EstadoSistema) -> dict:
    iteracao = int(state.get("iteracao_reflexion") or 0)
    prompt_usuario = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "DOCUMENTOS OFICIAIS RECUPERADOS (FONTE EXCLUSIVA DE VERDADE):\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
        + "\n\n---\nANÁLISE DE ELEGIBILIDADE ATUAL:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + f"\n\n---\nRESPOSTA AO CIDADÃO ATUAL (Iteração {iteracao}):\n{state.get('resposta_final', '')}"
    )
    try:
        critica, modelo_usado = invocar_estruturado(
            "reflexion_critico", AvaliacaoCriticaReflexion, PROMPT_REFLEXION_CRITICO, prompt_usuario
        )
    except Exception as erro:
        return _erro_api("reflexion_critico", erro)

    critica_dict = critica.model_dump()
    historico = list(state.get("historico_reflexion") or [])
    historico.append({"iteracao": iteracao, "modelo_critico": modelo_usado, **critica_dict})

    chave_agente = "reflexion_critico" if iteracao == 0 else f"reflexion_critico_{iteracao}"
    return {
        "critica_reflexion": critica_dict,
        "historico_reflexion": historico,
        "modelos_utilizados": _registrar_modelo(state, chave_agente, modelo_usado),
        "status_api": STATUS_SUCESSO,
    }


PROMPT_REFLEXION_REVISOR_ANALISE = f"""Você é o Agente Revisor Analítico (Reflexion) do assistente socioassistencial federal.
Corrija o parecer estruturado de elegibilidade aplicando rigorosamente as instruções do Auditor Crítico e usando EXCLUSIVAMENTE os DOCUMENTOS OFICIAIS RECUPERADOS.

{REGRAS_ANALISE_RIA02}"""

PROMPT_REFLEXION_REVISOR_TEXTO = f"""Você é o Agente Revisor de Comunicação (Reflexion) do assistente socioassistencial federal.
Reescreva a orientação ao cidadão aplicando integralmente TODAS as correções apontadas pelo Auditor Crítico, mantendo linguagem simples e ancoragem estrita nos documentos oficiais.

{REGRAS_COMUNICACAO_P02}"""


def agente_reflexion_revisor(state: EstadoSistema) -> dict:
    nova_iteracao = int(state.get("iteracao_reflexion") or 0) + 1
    critica = state.get("critica_reflexion") or {}
    contexto_base = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
        + "\n\n---\nANÁLISE DE ELEGIBILIDADE ANTERIOR:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + f"\n\nRESPOSTA ANTERIOR:\n{state.get('resposta_final', '')}\n\n"
        "---\nPARECER DO AUDITOR CRÍTICO (CORRIJA TODOS OS PONTOS ABAIXO):\n"
        + json.dumps(critica, ensure_ascii=False, indent=2)
    )
    try:
        analise_rev, mod_analise = invocar_estruturado(
            "reflexion_revisor", AnaliseElegibilidade, PROMPT_REFLEXION_REVISOR_ANALISE, contexto_base
        )
        analise_dump = analise_rev.model_dump()
        prompt_texto = (
            contexto_base
            + "\n\n---\nNOVA ANÁLISE DE ELEGIBILIDADE JÁ CORRIGIDA:\n"
            + json.dumps(analise_dump, ensure_ascii=False, indent=2)
        )
        texto_rev, mod_texto = invocar_texto(
            "reflexion_revisor", PROMPT_REFLEXION_REVISOR_TEXTO, prompt_texto
        )
    except Exception as erro:
        return _erro_api("reflexion_revisor", erro)

    chave_agente = f"reflexion_revisor_{nova_iteracao}"
    modelo_reg = mod_analise if mod_analise == mod_texto else f"{mod_analise} + {mod_texto}"
    return {
        "iteracao_reflexion": nova_iteracao,
        "analise_elegibilidade": analise_dump,
        "resposta_final": _garantir_aviso_institucional(texto_rev),
        "modelos_utilizados": _registrar_modelo(state, chave_agente, modelo_reg),
        "status_api": STATUS_SUCESSO,
    }
