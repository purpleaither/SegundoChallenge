"""Os 5 agentes (nós do LangGraph) do assistente socioassistencial.

Cada nó recebe o EstadoSistema e devolve apenas os campos que atualiza. Falhas de API são
convertidas em status_api="erro_api" + resposta_final explicativa; o grafo encerra o fluxo nesses casos.
"""

import json
from pathlib import Path
import sys
import warnings

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))
load_dotenv(PASTA_ATUAL / ".env")

from config import llm
from rag import recuperar_documentos_com_perfil, violacao_operacional_p02
from schemas import AnaliseElegibilidade, EstadoSistema, PerfilSocioeconomico, ValidacaoEscopo

MODELOS_FALLBACK = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
)
_llm_fallback = None
_usar_fallback = False


def _obter_llm_fallback(nome_modelo: str = MODELOS_FALLBACK[0]):
    global _llm_fallback
    if _llm_fallback is None or getattr(_llm_fallback, "model", None) != nome_modelo:
        _llm_fallback = ChatGoogleGenerativeAI(model=nome_modelo, max_retries=2)
    return _llm_fallback


def _eh_erro_modelo_indisponivel(erro: Exception) -> bool:
    msg = str(erro)
    return any(s in msg for s in ("NOT_FOUND", "no longer available", "404", "503", "UNAVAILABLE"))

STATUS_ERRO_API = "erro_api"
STATUS_BLOQUEADO = "bloqueado_guardrail"
STATUS_EM_PROCESSAMENTO = "em_processamento"
STATUS_SUCESSO = "sucesso"

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
    """Converte uma falha de chamada ao LLM em atualização de estado com mensagem clara."""
    return {
        "status_api": STATUS_ERRO_API,
        "motivo_rejeicao": f"Falha no agente '{agente}': {type(erro).__name__}: {str(erro)[:200]}",
        "resposta_final": (
            "Desculpe, não consegui concluir a sua orientação agora por uma falha técnica no serviço de "
            "inteligência artificial. Tente novamente em alguns minutos. Se precisar de ajuda imediata, "
            "procure o CRAS mais próximo da sua casa."
        ),
    }


def _invocar_estruturado(schema, prompt_sistema: str, prompt_usuario: str):
    global _usar_fallback
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]
    modelo = _obter_llm_fallback() if _usar_fallback else llm
    try:
        resultado = modelo.with_structured_output(schema).invoke(mensagens)
    except Exception as erro:
        if not _eh_erro_modelo_indisponivel(erro):
            raise
        _usar_fallback = True
        ultimo_erro = erro
        resultado = None
        for nome in MODELOS_FALLBACK:
            try:
                resultado = _obter_llm_fallback(nome).with_structured_output(schema).invoke(mensagens)
                break
            except Exception as err_fb:
                ultimo_erro = err_fb
        if resultado is None:
            raise ultimo_erro
    if resultado is None:
        raise ValueError(f"O modelo não retornou uma saída estruturada válida para {schema.__name__}.")
    return resultado


def _invocar_texto(prompt_sistema: str, prompt_usuario: str):
    global _usar_fallback
    mensagens = [SystemMessage(content=prompt_sistema), HumanMessage(content=prompt_usuario)]
    modelo = _obter_llm_fallback() if _usar_fallback else llm
    try:
        return modelo.invoke(mensagens)
    except Exception as erro:
        if not _eh_erro_modelo_indisponivel(erro):
            raise
        _usar_fallback = True
        ultimo_erro = erro
        for nome in MODELOS_FALLBACK:
            try:
                return _obter_llm_fallback(nome).invoke(mensagens)
            except Exception as err_fb:
                ultimo_erro = err_fb
        raise ultimo_erro


# ---------------------------------------------------------------------------
# Agente 1 — Guardrail (RIA07 / P02)
# ---------------------------------------------------------------------------
PROMPT_GUARDRAIL = """Você é o Guardrail de um assistente público, exclusivamente informativo, sobre programas e benefícios sociais federais do Brasil.
Sua única tarefa é classificar a intenção da mensagem do cidadão.

Marque eh_valido=True (tipo_bloqueio=None) quando a mensagem:
- relatar situação socioeconômica, familiar, de vulnerabilidade, saúde, deficiência, moradia, educação, trabalho/desemprego/renda, alimentação, água/luz/gás ou vida na zona rural; OU
- trouxer dúvidas informativas sobre programas, benefícios, auxílios, descontos, isenções ou direitos sociais (como funcionam, quem pode, qual a lei, onde pedir).
A linguagem costuma ser popular e informal ("tô sem emprego", "moro na roça", "botijão"): isso é válido.

Marque eh_valido=False quando:
1. tipo_bloqueio="fora_de_escopo": o assunto não tem relação com direitos ou benefícios sociais (ex.: receitas de culinária, futebol/esportes, piadas, programação, previsão do tempo, filmes, curiosidades gerais).
2. tipo_bloqueio="operacao_proibida_cpf_cadastro": o cidadão pede uma OPERAÇÃO que o sistema não realiza: consultar CPF ou o CadÚnico, verificar se o benefício DELE foi aprovado/está ativo, fazer/atualizar cadastro pelo chat ou aprovar/conceder benefício. Isso vale mesmo que ele cite um programa social.
   Perguntas informativas como "como faço para me inscrever no CadÚnico?" ou "onde atualizo meu cadastro?" são VÁLIDAS.

Escreva o motivo em uma frase curta, em português."""


def agente_guardrail(state: EstadoSistema) -> dict:
    mensagem = state["mensagem_usuario"]
    try:
        if violacao_operacional_p02(mensagem):
            validacao = ValidacaoEscopo(
                eh_valido=False,
                motivo="Pedido de consulta de CPF/CadÚnico, aprovação ou cadastro (vedado por P02).",
                tipo_bloqueio="operacao_proibida_cpf_cadastro",
            )
        else:
            validacao = _invocar_estruturado(ValidacaoEscopo, PROMPT_GUARDRAIL, f"Mensagem do cidadão:\n{mensagem}")
    except Exception as erro:  # falha de API: encerra sem prosseguir (fail-closed)
        return {"dentro_do_escopo": False, **_erro_api("guardrail", erro)}

    if validacao.eh_valido:
        return {"dentro_do_escopo": True, "motivo_rejeicao": None, "status_api": STATUS_EM_PROCESSAMENTO}

    proibida = validacao.tipo_bloqueio == "operacao_proibida_cpf_cadastro"
    return {
        "dentro_do_escopo": False,
        "motivo_rejeicao": validacao.motivo,
        "status_api": STATUS_BLOQUEADO,
        "resposta_final": MENSAGEM_OPERACAO_PROIBIDA if proibida else MENSAGEM_FORA_DE_ESCOPO,
    }


# ---------------------------------------------------------------------------
# Agente 2 — Extrator de Perfil (RIA01)
# ---------------------------------------------------------------------------
PROMPT_EXTRATOR = """Você é um assistente social técnico que lê o relato livre de um cidadão e extrai seu perfil socioeconômico estruturado.

Regras:
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


def agente_extrator_perfil(state: EstadoSistema) -> dict:
    try:
        perfil = _invocar_estruturado(
            PerfilSocioeconomico, PROMPT_EXTRATOR, f"Relato do cidadão:\n{state['mensagem_usuario']}"
        )
    except Exception as erro:
        return _erro_api("extrator_perfil", erro)
    return {"perfil_extraido": perfil.model_dump()}


# ---------------------------------------------------------------------------
# Agente 3 — Retriever (ChromaDB + filtros)
# ---------------------------------------------------------------------------
def agente_retriever(state: EstadoSistema) -> dict:
    try:
        resultado = recuperar_documentos_com_perfil(state["mensagem_usuario"], state.get("perfil_extraido"))
    except Exception as erro:
        return _erro_api("retriever", erro)
    return {"query_busca": resultado["query_busca"], "documentos_encontrados": resultado["documentos"]}


# ---------------------------------------------------------------------------
# Agente 4 — Analista de Elegibilidade (RIA02)
# ---------------------------------------------------------------------------
PROMPT_ANALISTA = """Você é um Analista de Elegibilidade de programas sociais federais. Você cruza os critérios legais dos DOCUMENTOS OFICIAIS RECUPERADOS com o perfil do cidadão.

Ancoragem estrita (RIA02) — regras obrigatórias:
1. Analise EXCLUSIVAMENTE os programas presentes nos documentos fornecidos. Avalie todos eles e não acrescente nenhum outro programa.
2. Para cada programa, compare a seção "## Quem pode" (Público-alvo, Critérios, Situação do critério) e a seção "## Legislação" (Lei base, Regulamentação, Atualização recente, Observações) com os dados do cidadão.
3. Classifique status_elegibilidade:
   - "elegivel": o perfil declarado atende a todos os requisitos explícitos do documento.
   - "potencialmente_elegivel": o programa tem relação com a necessidade e parte dos requisitos bate, mas algo precisa ser comprovado ou confirmado (ex.: renda, inscrição no CadÚnico).
   - "criterio_nao_especificado_na_base": o programa tem relação com a necessidade, mas o documento traz "Não especificado no documento de origem" ou "Informação parcial no documento" nos critérios.
   - "inelegivel": o programa não tem relação com a necessidade do cidadão ou há impedimento claro no documento.
4. NUNCA invente limites de renda, idades, valores, prazos ou regras que não estejam escritos no documento. Se o documento não detalha, registre isso literalmente em observacoes_documentais (ex.: "Critérios: Não especificado no documento de origem.").
5. Copie LITERALMENTE: nome_programa (título "# ..." do documento), orgao_responsavel (campo "Órgão responsável") e base_legal (Lei base; Regulamentação; Atualização recente — mantenha as normas de 2024–2026 citadas).
6. criterios_atendidos: somente requisitos do documento que os dados do cidadão já satisfazem. criterios_pendentes_ou_impeditivos: o que precisa ser comprovado/confirmado ou impede o acesso.
7. resumo_parecer: parecer técnico curto, em português, destacando os programas mais pertinentes e as lacunas da base."""


def agente_analista_elegibilidade(state: EstadoSistema) -> dict:
    documentos = state.get("documentos_encontrados") or []
    if not documentos:
        analise = AnaliseElegibilidade(
            programas_avaliados=[],
            resumo_parecer="Nenhum documento suficientemente relevante foi recuperado da base oficial para esta situação.",
        )
        return {"analise_elegibilidade": analise.model_dump()}

    prompt_usuario = (
        "DOCUMENTOS OFICIAIS RECUPERADOS DA BASE HOMOLOGADA:\n\n"
        + "\n\n".join(documentos)
        + "\n\n---\nPERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + f"\n\nRELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}"
    )
    try:
        analise = _invocar_estruturado(AnaliseElegibilidade, PROMPT_ANALISTA, prompt_usuario)
    except Exception as erro:
        return _erro_api("analista_elegibilidade", erro)
    return {"analise_elegibilidade": analise.model_dump()}


# ---------------------------------------------------------------------------
# Agente 5 — Comunicador (linguagem simples + P02)
# ---------------------------------------------------------------------------
PROMPT_COMUNICADOR = f"""Você é o Comunicador do Assistente Virtual Tira-Dúvidas sobre programas sociais federais. Você fala diretamente com cidadãos em situação de vulnerabilidade.

Tom de voz: acolhedor, empático, respeitoso, claro e direto. Frases curtas, sem jargão burocrático. Trate a pessoa por "você".

Regras obrigatórias:
1. Use APENAS os programas e informações do PARECER DO ANALISTA e dos DOCUMENTOS OFICIAIS fornecidos (RIA02). Não invente programas, valores, limites de renda, prazos ou leis.
2. Foque nos programas com status "elegivel", "potencialmente_elegivel" ou "criterio_nao_especificado_na_base". Não apresente os "inelegivel".
3. Para cada programa apresentado, traduza o "juridiquês" para o que ele significa na prática, mantendo: o nome oficial do programa, o órgão responsável e a legislação citada (lei base e atualização recente, quando houver).
4. Transparência: quando um critério constar como não especificado ou parcial na base, diga com simplicidade que as regras detalhadas devem ser confirmadas no atendimento presencial (CRAS ou órgão responsável).
5. Se nenhum programa for pertinente, diga isso com honestidade e oriente a procurar o CRAS para uma avaliação completa.
6. Inclua uma seção com o título "**Próximos passos práticos**", numerada, com ações concretas, por exemplo:
   1. Vá ao CRAS mais próximo da sua casa...
   2. Verifique ou atualize seu Cadastro Único (CadÚnico)...
   3. Leve documentos básicos: documento com foto e CPF de todos da família, comprovante de residência (ou declaração) e, se tiver, comprovantes de renda...
   Adapte os passos aos programas apresentados (ex.: órgão específico quando não for o CRAS).
7. Termine SEMPRE com este aviso, literalmente: "{AVISO_INSTITUCIONAL}"
8. Responda em português, em Markdown simples (títulos curtos, listas)."""


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
        resposta = _invocar_texto(PROMPT_COMUNICADOR, prompt_usuario)
        texto = resposta.text.strip()
        if not texto:
            raise ValueError("O modelo retornou uma resposta vazia.")
    except Exception as erro:
        return _erro_api("comunicador", erro)

    # Garante o aviso obrigatório (P02) mesmo se o modelo o omitir.
    if AVISO_INSTITUCIONAL not in texto:
        texto = f"{texto}\n\n{AVISO_INSTITUCIONAL}"
    return {"resposta_final": texto, "status_api": STATUS_SUCESSO}
