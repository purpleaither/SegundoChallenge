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

if __package__:
    from .config import (
        eh_modelo_secundario_local,
        invocar_estruturado,
        invocar_texto,
        sanitizar_mensagem_erro,
    )
    from .rag import (
        compor_resposta_deterministica_rag,
        contem_dados_ou_pedido_p02,
        detectar_situacao_critica_deterministica,
        eh_indicio_fraude_ou_ilicito,
        eh_pedido_ilicito_explicito,
        executar_buscas_rewoo,
        inferir_categoria_sensivel_fallback,
        neutralizar_trechos_criticos_para_extracao,
        possui_contexto_socioeconomico,
        recuperar_documentos_com_perfil,
        violacao_operacional_p02,
    )
    from .schemas import (
        CATEGORIAS_ENCAMINHAMENTO_AJUDA,
        STATUS_BLOQUEADO,
        STATUS_DEGRADADO,
        STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA,
        STATUS_EM_PROCESSAMENTO,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        STATUS_SUCESSO,
        STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA,
        AnaliseElegibilidade,
        AvaliacaoCriticaReflexion,
        CategoriaEncaminhamentoAjuda,
        EstadoSistema,
        PerfilSocioeconomico,
        PlanoReWOO,
        ValidacaoEscopo,
    )
else:
    from config import (
        eh_modelo_secundario_local,
        invocar_estruturado,
        invocar_texto,
        sanitizar_mensagem_erro,
    )
    from rag import (
        compor_resposta_deterministica_rag,
        contem_dados_ou_pedido_p02,
        detectar_situacao_critica_deterministica,
        eh_indicio_fraude_ou_ilicito,
        eh_pedido_ilicito_explicito,
        executar_buscas_rewoo,
        inferir_categoria_sensivel_fallback,
        neutralizar_trechos_criticos_para_extracao,
        possui_contexto_socioeconomico,
        recuperar_documentos_com_perfil,
        violacao_operacional_p02,
    )
    from schemas import (
        CATEGORIAS_ENCAMINHAMENTO_AJUDA,
        STATUS_BLOQUEADO,
        STATUS_DEGRADADO,
        STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA,
        STATUS_EM_PROCESSAMENTO,
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_ERRO_API,
        STATUS_SUCESSO,
        STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA,
        AnaliseElegibilidade,
        AvaliacaoCriticaReflexion,
        CategoriaEncaminhamentoAjuda,
        EstadoSistema,
        PerfilSocioeconomico,
        PlanoReWOO,
        ValidacaoEscopo,
    )

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

MENSAGEM_AJUDA_AUTOEXTERMINIO = (
    "Sinto muito que você esteja passando por um momento tão difícil. A sua vida importa e você não precisa "
    "enfrentar essa dor sem apoio.\n\n"
    "Este assistente é apenas informativo sobre programas sociais, mas existem serviços públicos e gratuitos "
    "prontos para acolher e ajudar você agora mesmo:\n\n"
    "- **CVV — Centro de Valorização da Vida (Ligue 188)**: atendimento gratuito, sigiloso e disponível 24 horas "
    "por dia em todo o Brasil, também por chat no site oficial **https://cvv.org.br**.\n"
    "- **SAMU (Ligue 192)** ou **Corpo de Bombeiros (Ligue 193)**: procure imediatamente em caso de emergência "
    "ou risco imediato à sua integridade.\n"
    "- **Rede de Saúde Pública (SUS)**: procure o **CAPS (Centro de Atenção Psicossocial)**, uma **UPA 24h** "
    "ou a **UBS (Posto de Saúde)** mais próxima da sua casa para cuidado presencial gratuito.\n"
    "- **CRAS / CREAS**: unidades da Assistência Social que também podem oferecer acolhimento e orientação "
    "presencial para você e sua família.\n\n"
    "Por favor, entre em contato com um desses canais ou peça apoio a alguém de sua confiança agora."
)

MENSAGEM_AJUDA_CODIGO_PENAL = (
    "Entendo a gravidade do que foi trazido, mas preciso esclarecer com respeito que este assistente é "
    "exclusivamente informativo sobre programas sociais: ele não registra ocorrências policiais, não substitui "
    "órgãos de proteção e jamais pode apoiar ou orientar práticas ilícitas.\n\n"
    "Se você ou alguém próximo estiver sofrendo violência, ameaça, crime ou violação de direitos, ou precisar "
    "de orientação jurídica gratuita, procure os canais oficiais:\n\n"
    "- **Polícia Militar (Ligue 190)**: para emergência, agressão em andamento ou risco imediato.\n"
    "- **Polícia Civil / Delegacia mais próxima (Disque 197)**: para registrar boletim de ocorrência e investigação.\n"
    "- **Central de Atendimento à Mulher (Ligue 180)**: orientação e denúncia gratuita 24h em casos de "
    "violência doméstica e familiar.\n"
    "- **Disque Direitos Humanos (Disque 100)**: denúncias de violações contra crianças, adolescentes, pessoas "
    "idosas, pessoas com deficiência e população em vulnerabilidade.\n"
    "- **Disque-Denúncia (181)**: para comunicar ilícitos de forma anônima.\n"
    "- **CREAS (Centro de Referência Especializado de Assistência Social)**: acompanhamento socioassistencial "
    "especializado a vítimas de violência ou violação de direitos (e **CRAS** para orientação sobre benefícios).\n"
    "- **Defensoria Pública (Ligue 129)**: orientação e assistência jurídica pública e gratuita."
)

MENSAGEM_AJUDA_COOCORRENCIA = (
    "Sinto muito pelo sofrimento e pela situação grave que você está vivendo. A sua vida e a sua segurança "
    "vêm em primeiro lugar, e você não precisa enfrentar isso sem ajuda.\n\n"
    "Este assistente é apenas informativo sobre programas sociais (não registra ocorrências nem apoia atos "
    "ilícitos), mas há canais públicos gratuitos para acolher e proteger você imediatamente:\n\n"
    "**1. Apoio imediato à vida e à saúde**\n"
    "- **CVV — Centro de Valorização da Vida (Ligue 188)**: apoio emocional gratuito, sigiloso e 24h em todo o "
    "Brasil, ou via chat em **https://cvv.org.br**.\n"
    "- **SAMU (Ligue 192)** ou **Corpo de Bombeiros (Ligue 193)**: socorro imediato em caso de emergência médica.\n"
    "- **CAPS (Centro de Atenção Psicossocial)**, **UPA 24h** ou **UBS (Posto de Saúde)** pelo **SUS**.\n\n"
    "**2. Proteção urgente, denúncia e assistência gratuita**\n"
    "- **Polícia Militar (Ligue 190)** para perigo ou agressão imediata e **Polícia Civil / Delegacia (Disque 197)** "
    "ou **Disque-Denúncia (181)** para ocorrência.\n"
    "- **Central de Atendimento à Mulher (Ligue 180)** para violência doméstica/familiar e **Disque Direitos "
    "Humanos (Disque 100)** para violações de direitos.\n"
    "- **CREAS / CRAS** para proteção socioassistencial especializada e **Defensoria Pública (Ligue 129)** para "
    "orientação jurídica gratuita."
)

AVISO_PRIVACIDADE_DADOS_SENSIVEIS = (
    "Observação de privacidade: este assistente não consulta CPF nem o CadÚnico e não realiza cadastros. "
    "Por sua segurança, não compartilhe CPF ou documentos pessoais neste chat; apresente-os apenas diretamente "
    "nos canais oficiais de atendimento."
)

MENSAGENS_ENCAMINHAMENTO_AJUDA: dict[CategoriaEncaminhamentoAjuda, str] = {
    "autoexterminio": MENSAGEM_AJUDA_AUTOEXTERMINIO,
    "codigo_penal": MENSAGEM_AJUDA_CODIGO_PENAL,
    "autoexterminio_e_codigo_penal": MENSAGEM_AJUDA_COOCORRENCIA,
}

_MOTIVOS_DETERMINISTICOS_AJUDA: dict[CategoriaEncaminhamentoAjuda, str] = {
    "autoexterminio": (
        "Identificado sinal crítico de autoextermínio ou autolesão; realizado encaminhamento imediato para "
        "canais oficiais de apoio à vida."
    ),
    "codigo_penal": (
        "Identificada situação que envolve matéria do Código Penal (violência, violação de direitos ou ilícito); "
        "realizado encaminhamento para canais oficiais de proteção e orientação."
    ),
    "autoexterminio_e_codigo_penal": (
        "Identificada coocorrência de risco de autoextermínio e matéria penal; realizado encaminhamento "
        "prioritário para preservação da vida e proteção oficial."
    ),
}


def _erro_api(agente: str, erro: Exception) -> dict:
    """Converte uma falha de chamada ao LLM/RAG em atualização de estado fail-closed sanitizada."""
    return {
        "status_api": STATUS_ERRO_API,
        "motivo_rejeicao": f"Falha no agente '{agente}': {sanitizar_mensagem_erro(erro)}",
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


def _registrar_evento_fallback(state: EstadoSistema, evento: str) -> list[str]:
    """Registra evento sanitizado de contingência/degradação sem armazenar dados sensíveis do cidadão."""
    eventos = list(state.get("eventos_fallback") or [])
    eventos.append(evento)
    return eventos


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
# Agente 1 — Guardrail + Seletor de Padrão de Execução (RIA06 / RIA07 / P02)
# ---------------------------------------------------------------------------
PROMPT_GUARDRAIL = """Você é o Guardrail e Seletor de Arquitetura de um assistente público, exclusivamente informativo, sobre programas e benefícios sociais federais do Brasil.
Você avalia TRÊS dimensões complementares: (A1) necessidade de apoio/proteção especial, (A2) validade de escopo socioassistencial e (B) padrão ideal de execução quando houver escopo válido.

REGRA CRÍTICA ANTIFALSO-POSITIVO (LINGUAGEM POPULAR E SAÚDE):
- Expressões figuradas e metáforas coloquiais de aperto socioeconômico NÃO são autoextermínio nem crime. Exemplos com categoria_encaminhamento=None e eh_valido=True: "a conta de luz está me matando", "as dívidas estão me matando", "estou morrendo de preocupação com o aluguel", "me matando de trabalhar", "matar a fome dos meus filhos", "cortaram meu Bolsa Família".
- Dúvidas informativas de saúde ou deficiência sem ideação de autolesão (ex.: "faço tratamento de depressão no CAPS, tenho direito ao BPC ou remédio gratuito?") têm categoria_encaminhamento=None e eh_valido=True.

PARTE A1 — Detecção de Mensagem Adicional de Apoio/Proteção (categoria_encaminhamento):
Avalie independentemente de eh_valido:
- "autoexterminio_e_codigo_penal": coocorrência na mesma mensagem de risco real de autoextermínio/autolesão E elementos que ferem o Código Penal.
- "autoexterminio": ideação suicida, intenção de tirar a própria vida, automutilação/autolesão, pedido de métodos ou crise aguda ("quero morrer", "não aguento mais viver").
- "codigo_penal": elementos que ferem o Código Penal brasileiro — vítimas/relatos de violência doméstica/familiar, agressão física, ameaça, abuso/exploração sexual ou de vulneráveis, cárcere privado, trabalho análogo à escravidão, furto/roubo/extorsão, retenção criminosa de documentos/cartão de benefício, OU pedidos/relatos de prática de ilícito/fraude documental.
- None: quando não houver risco real de autoextermínio nem matéria penal.

PARTE A2 — Validação de Escopo para Orientação de Benefícios (eh_valido e tipo_bloqueio):
REGRA DE RESPOSTA DUPLA (BENEFÍCIOS + APOIO):
- Marque eh_valido=True (tipo_bloqueio=None) SEMPRE que a mensagem contiver situação socioeconômica, familiar, vulnerabilidade, saúde, deficiência, moradia, educação, trabalho/desemprego/renda, alimentação, zona rural OU dúvida informativa sobre programas sociais — MESMO QUE categoria_encaminhamento esteja preenchida com "autoexterminio", "codigo_penal" ou "autoexterminio_e_codigo_penal" (ex.: "sou mãe solteira, tenho 3 filhos, desempregada, não aguento mais quero morrer" -> eh_valido=True E categoria_encaminhamento="autoexterminio"; "meu marido me bate, saí de casa sem renda com meus filhos" -> eh_valido=True E categoria_encaminhamento="codigo_penal").
- Marque eh_valido=False (padrao_execucao=None, justificativa_padrao=None) APENAS quando:
  1. tipo_bloqueio="sem_escopo_socioeconomico": houver apenas crise de autoextermínio ou relato/ocorrência criminal isolada SEM qualquer contexto socioeconômico ou dúvida de benefício, OU quando a mensagem for um pedido de instrução para cometer fraude/ilícito penal (ex.: "como falsificar comprovante ou esconder salário para fraudar benefício").
  2. tipo_bloqueio="operacao_proibida_cpf_cadastro": pedido operacional vedado por P02 (consultar CPF/CadÚnico, verificar aprovação individual, fazer cadastro pelo chat). Perguntas informativas ("como me inscrevo no CadÚnico?") são VÁLIDAS.
  3. tipo_bloqueio="fora_de_escopo": assunto alheio a direitos/benefícios sociais sem crise nem crime (receitas, futebol/esportes, piadas, programação, filmes, curiosidades).

PARTE B — Seleção do Padrão de Execução (OBRIGATÓRIO quando eh_valido=True):
Escolha exatamente um valor para padrao_execucao e explique em justificativa_padrao (uma frase curta):
1. "padrao":
   - Dúvidas diretas sobre um único benefício ou tema específico; OU
   - Relatos socioeconômicos simples e lineares com poucas variáveis (ex.: mãe solo desempregada com filhos pedindo orientação básica).
2. "rewoo":
   - Relatos multifacetados combinando 3 ou mais vulnerabilidades/necessidades distintas no mesmo pedido (ex.: zona rural + seca + filhos na escola + idoso/pessoa com deficiência + luz/gás/moradia); OU
   - Perguntas amplas/comparativas que exigem decompor a busca em várias frentes independentes.
3. "reflexion":
   - Casos limítrofes, ambíguos ou com potenciais conflitos de regras e acumulação de benefícios (ex.: acumular BPC com Bolsa Família, renda no limite, MEI x benefício); OU
   - Pedidos com exigência explícita de detalhamento legal/normativo (leis, decretos, portarias de 2024–2026).

Escreva motivo e justificativa_padrao de forma objetiva, em português."""

NOTA_ORQUESTRACAO_APOIO_SEPARADO = (
    "\n\nNOTA DE ORQUESTRAÇÃO DO SISTEMA: Uma mensagem institucional separada com os canais oficiais de "
    "emergência, saúde mental e proteção legal (ex.: 188, 192, 190, 180, CREAS, Defensoria) já será exibida "
    "junto a esta resposta. Mantenha tom especialmente acolhedor e concentre este texto exclusivamente em "
    "orientar sobre os programas e benefícios sociais aplicáveis à situação socioeconômica e os próximos "
    "passos práticos no CRAS/órgão responsável."
)

SEPARADOR_MENSAGEM_APOIO = "\n\n---\n\n### Mensagem adicional de apoio e canais oficiais de ajuda\n\n"


def _combinar_categorias_apoio(
    *categorias: CategoriaEncaminhamentoAjuda | None,
) -> CategoriaEncaminhamentoAjuda | None:
    """Consolida sinais determinísticos e do LLM preservando coocorrência quando ambos os eixos aparecem."""
    tem_auto = any(c in ("autoexterminio", "autoexterminio_e_codigo_penal") for c in categorias if c)
    tem_penal = any(c in ("codigo_penal", "autoexterminio_e_codigo_penal") for c in categorias if c)
    if tem_auto and tem_penal:
        return "autoexterminio_e_codigo_penal"
    if tem_auto:
        return "autoexterminio"
    if tem_penal:
        return "codigo_penal"
    return None


def _montar_resposta_encaminhamento(categoria: CategoriaEncaminhamentoAjuda, mensagem_usuario: str) -> str:
    """Retorna a mensagem institucional acolhedora da categoria e anexa aviso de dados se houver CPF/P02."""
    texto_base = MENSAGENS_ENCAMINHAMENTO_AJUDA[categoria]
    if contem_dados_ou_pedido_p02(mensagem_usuario):
        return f"{texto_base}\n\n{AVISO_PRIVACIDADE_DADOS_SENSIVEIS}"
    return texto_base


def _resposta_estado_encaminhamento(
    state: EstadoSistema,
    categoria: CategoriaEncaminhamentoAjuda,
    motivo: str,
    modelo_registrado: str,
) -> dict:
    """Constrói atualização de EstadoSistema quando há apenas encaminhamento de ajuda sem fluxo de benefícios."""
    mensagem = state["mensagem_usuario"]
    apoio = _montar_resposta_encaminhamento(categoria, mensagem)
    return {
        "dentro_do_escopo": False,
        "motivo_rejeicao": motivo,
        "categoria_encaminhamento": categoria,
        "padrao_execucao": None,
        "justificativa_padrao": None,
        "modelos_utilizados": _registrar_modelo(state, "guardrail", modelo_registrado),
        "resposta_beneficios": None,
        "mensagem_apoio": apoio,
        "status_api": STATUS_ENCAMINHAMENTO_AJUDA,
        "resposta_final": apoio,
    }


def _eh_excecao_seguranca_llm(erro: Exception) -> bool:
    """Detecta falhas decorrentes de filtro de segurança ou resposta bloqueada/vazia no provedor LLM."""
    msg = str(erro).lower()
    sinais_seguranca = (
        "safety",
        "harm_category",
        "prohibited_content",
        "dangerous_content",
        "blocklist",
        "blocked",
        "finish_reason",
        "saída estruturada vazia",
        "saida estruturada vazia",
    )
    return any(sinal in msg for sinal in sinais_seguranca)


def _motivo_indica_pedido_ilicito(motivo: str) -> bool:
    """Verifica se a justificativa do LLM aponta tentativa/pedido de fraude ou ato ilícito."""
    m = (motivo or "").lower()
    return any(t in m for t in ("fraud", "falsific", "ilícit", "ilicit", "burlar", "omitir renda", "esconder sal"))


def _invocar_estruturado_resiliente(
    state: EstadoSistema,
    agente: str,
    schema: type,
    prompt_sistema: str,
    prompt_usuario: str,
):
    """Invoca saída estruturada e, em caso de bloqueio SAFETY em relato já acolhido, tenta texto neutralizado."""
    try:
        return invocar_estruturado(agente, schema, prompt_sistema, prompt_usuario)
    except Exception as erro:
        if state.get("categoria_encaminhamento") and _eh_excecao_seguranca_llm(erro):
            original = state["mensagem_usuario"]
            sanitizada = neutralizar_trechos_criticos_para_extracao(original)
            if sanitizada != original and original in prompt_usuario:
                return invocar_estruturado(
                    agente,
                    schema,
                    prompt_sistema,
                    prompt_usuario.replace(original, sanitizada),
                )
        raise


def _invocar_texto_resiliente(
    state: EstadoSistema,
    agente: str,
    prompt_sistema: str,
    prompt_usuario: str,
) -> tuple[str, str]:
    """Invoca geração textual e, em caso de bloqueio SAFETY em relato já acolhido, tenta texto neutralizado."""
    try:
        return invocar_texto(agente, prompt_sistema, prompt_usuario)
    except Exception as erro:
        if state.get("categoria_encaminhamento") and _eh_excecao_seguranca_llm(erro):
            original = state["mensagem_usuario"]
            sanitizada = neutralizar_trechos_criticos_para_extracao(original)
            if sanitizada != original and original in prompt_usuario:
                return invocar_texto(
                    agente,
                    prompt_sistema,
                    prompt_usuario.replace(original, sanitizada),
                )
        raise


def agente_guardrail(state: EstadoSistema) -> dict:
    mensagem = state["mensagem_usuario"]
    categoria_det = detectar_situacao_critica_deterministica(mensagem)
    indicio_sensivel = inferir_categoria_sensivel_fallback(mensagem)
    tem_violacao_p02 = violacao_operacional_p02(mensagem)
    tem_pedido_ilicito = eh_pedido_ilicito_explicito(mensagem)
    tem_contexto_socio = possui_contexto_socioeconomico(mensagem)

    # 1. Pedido explícito de prática de fraude/ilícito: nunca aciona orientação de como obter benefício
    if tem_pedido_ilicito:
        cat_ilicito = _combinar_categorias_apoio(categoria_det, "codigo_penal") or "codigo_penal"
        return _resposta_estado_encaminhamento(
            state=state,
            categoria=cat_ilicito,
            motivo=_MOTIVOS_DETERMINISTICOS_AJUDA[cat_ilicito],
            modelo_registrado="regra_deterministica_seguranca",
        )

    # 2. Pedido operacional P02 (consulta CPF/CadÚnico): ajuda prevalece se houver crise/crime explícito
    if tem_violacao_p02:
        if categoria_det is not None:
            return _resposta_estado_encaminhamento(
                state=state,
                categoria=categoria_det,
                motivo=_MOTIVOS_DETERMINISTICOS_AJUDA[categoria_det],
                modelo_registrado="regra_deterministica_seguranca",
            )
        if indicio_sensivel is None:
            return {
                "dentro_do_escopo": False,
                "motivo_rejeicao": "Pedido de consulta de CPF/CadÚnico, aprovação ou cadastro (vedado por P02).",
                "categoria_encaminhamento": None,
                "padrao_execucao": None,
                "justificativa_padrao": None,
                "modelos_utilizados": _registrar_modelo(state, "guardrail", "regra_deterministica_p02"),
                "resposta_beneficios": None,
                "mensagem_apoio": None,
                "status_api": STATUS_BLOQUEADO,
                "resposta_final": MENSAGEM_OPERACAO_PROIBIDA,
            }

    # 3. Crise/crime explícito SEM qualquer contexto socioeconômico: encaminha imediatamente à ajuda oficial
    if categoria_det is not None and not tem_contexto_socio:
        return _resposta_estado_encaminhamento(
            state=state,
            categoria=categoria_det,
            motivo=_MOTIVOS_DETERMINISTICOS_AJUDA[categoria_det],
            modelo_registrado="regra_deterministica_seguranca",
        )

    # 4. Classificação estruturada pelo LLM (avalia escopo, padrão e sinais sutis de apoio em paralelo)
    try:
        validacao, modelo_usado = invocar_estruturado(
            "guardrail", ValidacaoEscopo, PROMPT_GUARDRAIL, f"Mensagem do cidadão:\n{mensagem}"
        )
        modelos = _registrar_modelo(state, "guardrail", modelo_usado)
    except Exception as erro:  # fail-closed com salvaguarda para relatos sensíveis e fallback RAG seguro
        cat_fallback = _combinar_categorias_apoio(categoria_det, indicio_sensivel)
        suspeita_fraude = eh_indicio_fraude_ou_ilicito(mensagem)
        erro_sanitizado = sanitizar_mensagem_erro(erro)

        # Jamais orientar benefícios se houver suspeita de fraude/ilícito sob queda do LLM
        if suspeita_fraude:
            cat_fraude = _combinar_categorias_apoio(cat_fallback, "codigo_penal") or "codigo_penal"
            return _resposta_estado_encaminhamento(
                state=state,
                categoria=cat_fraude,
                motivo=_MOTIVOS_DETERMINISTICOS_AJUDA[cat_fraude],
                modelo_registrado="fallback_deterministico_seguranca",
            )

        # Salvaguarda de apoio para categoria explícita OU indício sensível (mesmo em 503/429)
        if cat_fallback is not None:
            if tem_contexto_socio and not tem_violacao_p02:
                eh_safety = _eh_excecao_seguranca_llm(erro)
                update_apoio = {
                    "dentro_do_escopo": True,
                    "motivo_rejeicao": _MOTIVOS_DETERMINISTICOS_AJUDA[cat_fallback],
                    "categoria_encaminhamento": cat_fallback,
                    "padrao_execucao": "padrao",
                    "justificativa_padrao": (
                        "Fluxo padrão ativado em contingência para preservar orientação de benefícios."
                        if eh_safety
                        else "Modo degradado ativado: busca direta nas fichas oficiais preservando apoio."
                    ),
                    "modelos_utilizados": _registrar_modelo(state, "guardrail", "fallback_deterministico_seguranca"),
                    "mensagem_apoio": _montar_resposta_encaminhamento(cat_fallback, mensagem),
                    "status_api": STATUS_EM_PROCESSAMENTO,
                }
                if not eh_safety:
                    update_apoio["modo_degradado"] = True
                    update_apoio["eventos_fallback"] = _registrar_evento_fallback(
                        state,
                        f"guardrail: indisponibilidade LLM ({erro_sanitizado}); contingência RAG com apoio preservado",
                    )
                return update_apoio
            return _resposta_estado_encaminhamento(
                state=state,
                categoria=cat_fallback,
                motivo=_MOTIVOS_DETERMINISTICOS_AJUDA[cat_fallback],
                modelo_registrado="fallback_deterministico_seguranca",
            )

        # Relato socioeconômico legítimo sem P02/ilícito: contingência determinística ancorada no RAG
        if tem_contexto_socio and not tem_violacao_p02:
            return {
                "dentro_do_escopo": True,
                "motivo_rejeicao": None,
                "categoria_encaminhamento": None,
                "padrao_execucao": "padrao",
                "justificativa_padrao": "Modo degradado ativado: busca direta nas fichas oficiais sem LLM.",
                "modelos_utilizados": _registrar_modelo(state, "guardrail", "fallback_deterministico_escopo"),
                "modo_degradado": True,
                "eventos_fallback": _registrar_evento_fallback(
                    state,
                    f"guardrail: indisponibilidade LLM ({erro_sanitizado}); ativado fallback determinístico RAG",
                ),
                "mensagem_apoio": None,
                "status_api": STATUS_EM_PROCESSAMENTO,
            }

        # Fora de escopo ou incerto: mantém fail-closed
        return {
            "dentro_do_escopo": False,
            "categoria_encaminhamento": None,
            "padrao_execucao": None,
            "justificativa_padrao": None,
            "resposta_beneficios": None,
            "mensagem_apoio": None,
            **_erro_api("guardrail", erro),
        }

    cat_llm: CategoriaEncaminhamentoAjuda | None = validacao.categoria_encaminhamento
    if cat_llm is None and validacao.tipo_bloqueio in CATEGORIAS_ENCAMINHAMENTO_AJUDA:
        cat_llm = validacao.tipo_bloqueio  # retrocompatibilidade caso o modelo preencha em tipo_bloqueio
    categoria_final = _combinar_categorias_apoio(categoria_det, cat_llm)

    if tem_violacao_p02:
        if categoria_final is not None:
            return _resposta_estado_encaminhamento(
                state=state,
                categoria=categoria_final,
                motivo=validacao.motivo,
                modelo_registrado=modelo_usado,
            )
        return {
            "dentro_do_escopo": False,
            "motivo_rejeicao": "Pedido de consulta de CPF/CadÚnico, aprovação ou cadastro (vedado por P02).",
            "categoria_encaminhamento": None,
            "padrao_execucao": None,
            "justificativa_padrao": None,
            "modelos_utilizados": modelos,
            "resposta_beneficios": None,
            "mensagem_apoio": None,
            "status_api": STATUS_BLOQUEADO,
            "resposta_final": MENSAGEM_OPERACAO_PROIBIDA,
        }

    resgate_socioeconomico = (
        categoria_final is not None
        and tem_contexto_socio
        and validacao.tipo_bloqueio != "fora_de_escopo"
        and not _motivo_indica_pedido_ilicito(validacao.motivo)
    )

    if validacao.eh_valido or resgate_socioeconomico:
        padrao = validacao.padrao_execucao or "padrao"
        justificativa = validacao.justificativa_padrao or validacao.motivo
        eventos = list(state.get("eventos_fallback") or [])
        if eh_modelo_secundario_local(modelo_usado) and padrao in ("rewoo", "reflexion"):
            eventos.append(
                f"guardrail: fallback local ({modelo_usado}) ativo; simplificado padrão '{padrao}' para 'padrao'"
            )
            justificativa = f"{justificativa} (simplificado para fluxo padrão no fallback local)"
            padrao = "padrao"
        apoio = _montar_resposta_encaminhamento(categoria_final, mensagem) if categoria_final else None
        return {
            "dentro_do_escopo": True,
            "motivo_rejeicao": validacao.motivo if categoria_final else None,
            "categoria_encaminhamento": categoria_final,
            "padrao_execucao": padrao,
            "justificativa_padrao": justificativa,
            "modelos_utilizados": modelos,
            "eventos_fallback": eventos,
            "mensagem_apoio": apoio,
            "status_api": STATUS_EM_PROCESSAMENTO,
        }

    if categoria_final is not None:
        return _resposta_estado_encaminhamento(
            state=state,
            categoria=categoria_final,
            motivo=validacao.motivo,
            modelo_registrado=modelo_usado,
        )

    proibida = validacao.tipo_bloqueio == "operacao_proibida_cpf_cadastro"
    return {
        "dentro_do_escopo": False,
        "motivo_rejeicao": validacao.motivo,
        "categoria_encaminhamento": None,
        "padrao_execucao": None,
        "justificativa_padrao": None,
        "modelos_utilizados": modelos,
        "resposta_beneficios": None,
        "mensagem_apoio": None,
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
        perfil, modelo_usado = _invocar_estruturado_resiliente(
            state,
            "extrator_perfil",
            PerfilSocioeconomico,
            PROMPT_EXTRATOR,
            f"Relato do cidadão:\n{state['mensagem_usuario']}",
        )
    except Exception as erro:
        mensagem = state["mensagem_usuario"]
        if state.get("dentro_do_escopo") and not eh_indicio_fraude_ou_ilicito(mensagem):
            return {
                "perfil_extraido": None,
                "modo_degradado": True,
                "eventos_fallback": _registrar_evento_fallback(
                    state,
                    f"extrator_perfil: indisponibilidade LLM ({sanitizar_mensagem_erro(erro)}); "
                    "busca RAG direta sem extração estruturada",
                ),
                "modelos_utilizados": _registrar_modelo(state, "extrator_perfil", "fallback_sem_extracao"),
            }
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
        analise, modelo_usado = _invocar_estruturado_resiliente(
            state, "analista_elegibilidade", AnaliseElegibilidade, PROMPT_ANALISTA, prompt_usuario
        )
    except Exception as erro:
        return {
            "modo_degradado": True,
            "eventos_fallback": _registrar_evento_fallback(
                state,
                f"analista_elegibilidade: indisponibilidade LLM ({sanitizar_mensagem_erro(erro)}); "
                "síntese determinística sobre fichas já recuperadas",
            ),
            "modelos_utilizados": _registrar_modelo(state, "analista_elegibilidade", "fallback_deterministico_rag"),
        }
    return {
        "analise_elegibilidade": analise.model_dump(),
        "modelos_utilizados": _registrar_modelo(state, "analista_elegibilidade", modelo_usado),
    }


PROMPT_COMUNICADOR = f"""Você é o Comunicador do Assistente Virtual Tira-Dúvidas sobre programas sociais federais. Você fala diretamente com cidadãos em situação de vulnerabilidade.

{REGRAS_COMUNICACAO_P02}"""


def agente_comunicador(state: EstadoSistema) -> dict:
    nota_apoio = NOTA_ORQUESTRACAO_APOIO_SEPARADO if state.get("categoria_encaminhamento") else ""
    prompt_usuario = (
        f"MENSAGEM DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + "\n\nPARECER DO ANALISTA DE ELEGIBILIDADE:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
        + nota_apoio
    )
    try:
        texto, modelo_usado = _invocar_texto_resiliente(state, "comunicador", PROMPT_COMUNICADOR, prompt_usuario)
    except Exception as erro:
        return {
            "modo_degradado": True,
            "eventos_fallback": _registrar_evento_fallback(
                state,
                f"comunicador: indisponibilidade LLM ({sanitizar_mensagem_erro(erro)}); "
                "formatação determinística do parecer/fichas",
            ),
            "modelos_utilizados": _registrar_modelo(state, "comunicador", "fallback_deterministico_rag"),
        }

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
        plano, modelo_usado = _invocar_estruturado_resiliente(
            state,
            "rewoo_planner",
            PlanoReWOO,
            PROMPT_REWOO_PLANNER,
            f"Relato multifacetado / dúvida do cidadão:\n{state['mensagem_usuario']}",
        )
    except Exception as erro:
        return {
            "padrao_execucao": "padrao",
            "justificativa_padrao": "Downgrade automático de ReWOO para fluxo padrão após falha no planejador.",
            "eventos_fallback": _registrar_evento_fallback(
                state,
                f"rewoo_planner: indisponibilidade/falha LLM ({sanitizar_mensagem_erro(erro)}); "
                "downgrade para fluxo 'padrao'",
            ),
            "modelos_utilizados": _registrar_modelo(state, "rewoo_planner", "downgrade_para_padrao"),
        }

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
    nota_apoio = NOTA_ORQUESTRACAO_APOIO_SEPARADO if state.get("categoria_encaminhamento") else ""
    prompt_analise = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + f"\n\nMAPA DO PLANO ReWOO (#E1..#En):\n{mapa_plano}\n\n"
        "DOCUMENTOS OFICIAIS CONSOLIDADOS (ÚNICA FONTE DE VERDADE — RIA02):\n\n"
        + "\n\n".join(documentos)
    )
    try:
        analise, modelo_analise = _invocar_estruturado_resiliente(
            state, "rewoo_solver", AnaliseElegibilidade, PROMPT_REWOO_SOLVER_ANALISE, prompt_analise
        )
    except Exception as erro:
        return {
            "modo_degradado": True,
            "eventos_fallback": _registrar_evento_fallback(
                state,
                f"rewoo_solver: indisponibilidade LLM na análise ({sanitizar_mensagem_erro(erro)}); "
                "síntese determinística sobre fichas recuperadas",
            ),
            "modelos_utilizados": _registrar_modelo(state, "rewoo_solver", "fallback_deterministico_rag"),
        }

    analise_dump = analise.model_dump()
    modelos = _registrar_modelo(state, "rewoo_solver", modelo_analise)

    prompt_sintese = (
        f"MENSAGEM DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        f"MAPA DAS NECESSIDADES INVESTIGADAS (ReWOO):\n{mapa_plano}\n\n"
        "PERFIL EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + "\n\nPARECER DO SOLVER DE ELEGIBILIDADE:\n"
        + json.dumps(analise_dump, ensure_ascii=False, indent=2)
        + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
        + "\n\n".join(documentos)
        + nota_apoio
    )
    try:
        texto_sintese, modelo_sintese = _invocar_texto_resiliente(
            state, "comunicador", PROMPT_COMUNICADOR, prompt_sintese
        )
    except Exception as erro:
        modelos["rewoo_comunicador"] = "fallback_deterministico_rag"
        return {
            "analise_elegibilidade": analise_dump,
            "modo_degradado": True,
            "eventos_fallback": _registrar_evento_fallback(
                state,
                f"rewoo_comunicador: indisponibilidade LLM ({sanitizar_mensagem_erro(erro)}); "
                "preservada análise do solver com formatação determinística",
            ),
            "modelos_utilizados": modelos,
        }

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
    chave_agente = "reflexion_critico" if iteracao == 0 else f"reflexion_critico_{iteracao}"
    prompt_usuario = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "DOCUMENTOS OFICIAIS RECUPERADOS (FONTE EXCLUSIVA DE VERDADE):\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
        + "\n\n---\nANÁLISE DE ELEGIBILIDADE ATUAL:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + f"\n\n---\nRESPOSTA AO CIDADÃO ATUAL (Iteração {iteracao}):\n{state.get('resposta_final', '')}"
    )
    try:
        critica, modelo_usado = _invocar_estruturado_resiliente(
            state, "reflexion_critico", AvaliacaoCriticaReflexion, PROMPT_REFLEXION_CRITICO, prompt_usuario
        )
    except Exception as erro:
        resposta_existente = (state.get("resposta_final") or "").strip()
        if resposta_existente:
            historico = list(state.get("historico_reflexion") or [])
            historico.append(
                {
                    "iteracao": iteracao,
                    "modelo_critico": "ignorado_indisponibilidade_llm",
                    "aprovado": True,
                    "problemas_encontrados": [],
                    "instrucoes_correcao": "",
                    "observacao": "Auditoria Reflexion ignorada por indisponibilidade do LLM; resposta validada preservada.",
                }
            )
            return {
                "critica_reflexion": {
                    "aprovado": True,
                    "problemas_encontrados": [],
                    "instrucoes_correcao": "",
                },
                "historico_reflexion": historico,
                "resposta_final": _garantir_aviso_institucional(resposta_existente),
                "modo_degradado": True,
                "eventos_fallback": _registrar_evento_fallback(
                    state,
                    f"{chave_agente}: indisponibilidade LLM ({sanitizar_mensagem_erro(erro)}); "
                    "preservada resposta validada do comunicador",
                ),
                "modelos_utilizados": _registrar_modelo(state, chave_agente, "ignorado_indisponibilidade_llm"),
                "status_api": STATUS_DEGRADADO,
            }
        return _erro_api("reflexion_critico", erro)

    critica_dict = critica.model_dump()
    historico = list(state.get("historico_reflexion") or [])
    historico.append({"iteracao": iteracao, "modelo_critico": modelo_usado, **critica_dict})

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
    chave_agente = f"reflexion_revisor_{nova_iteracao}"
    critica = state.get("critica_reflexion") or {}
    nota_apoio = NOTA_ORQUESTRACAO_APOIO_SEPARADO if state.get("categoria_encaminhamento") else ""
    resposta_anterior = (state.get("resposta_final") or "").strip()
    contexto_base = (
        f"RELATO ORIGINAL DO CIDADÃO:\n{state['mensagem_usuario']}\n\n"
        "PERFIL SOCIOECONÔMICO EXTRAÍDO:\n"
        + json.dumps(state.get("perfil_extraido") or {}, ensure_ascii=False, indent=2)
        + "\n\nDOCUMENTOS OFICIAIS RECUPERADOS:\n\n"
        + ("\n\n".join(state.get("documentos_encontrados") or []) or "Nenhum documento recuperado.")
        + "\n\n---\nANÁLISE DE ELEGIBILIDADE ANTERIOR:\n"
        + json.dumps(state.get("analise_elegibilidade") or {}, ensure_ascii=False, indent=2)
        + f"\n\nRESPOSTA ANTERIOR:\n{resposta_anterior}\n\n"
        "---\nPARECER DO AUDITOR CRÍTICO (CORRIJA TODOS OS PONTOS ABAIXO):\n"
        + json.dumps(critica, ensure_ascii=False, indent=2)
    )
    try:
        analise_rev, mod_analise = _invocar_estruturado_resiliente(
            state, "reflexion_revisor", AnaliseElegibilidade, PROMPT_REFLEXION_REVISOR_ANALISE, contexto_base
        )
    except Exception as erro:
        if resposta_anterior:
            return {
                "resposta_final": _garantir_aviso_institucional(resposta_anterior),
                "modo_degradado": True,
                "eventos_fallback": _registrar_evento_fallback(
                    state,
                    f"{chave_agente}: indisponibilidade LLM na revisão analítica ({sanitizar_mensagem_erro(erro)}); "
                    "preservada resposta anterior validada",
                ),
                "modelos_utilizados": _registrar_modelo(state, chave_agente, "ignorado_indisponibilidade_llm"),
                "status_api": STATUS_DEGRADADO,
            }
        return _erro_api("reflexion_revisor", erro)

    analise_dump = analise_rev.model_dump()
    prompt_texto = (
        contexto_base
        + "\n\n---\nNOVA ANÁLISE DE ELEGIBILIDADE JÁ CORRIGIDA:\n"
        + json.dumps(analise_dump, ensure_ascii=False, indent=2)
        + nota_apoio
    )
    try:
        texto_rev, mod_texto = _invocar_texto_resiliente(
            state, "reflexion_revisor", PROMPT_REFLEXION_REVISOR_TEXTO, prompt_texto
        )
    except Exception as erro:
        if resposta_anterior:
            return {
                "analise_elegibilidade": analise_dump,
                "resposta_final": _garantir_aviso_institucional(resposta_anterior),
                "modo_degradado": True,
                "eventos_fallback": _registrar_evento_fallback(
                    state,
                    f"{chave_agente}: indisponibilidade LLM na reescrita ({sanitizar_mensagem_erro(erro)}); "
                    "preservada resposta anterior validada",
                ),
                "modelos_utilizados": _registrar_modelo(
                    state, chave_agente, f"{mod_analise} + ignorado_indisponibilidade_llm"
                ),
                "status_api": STATUS_DEGRADADO,
            }
        return _erro_api("reflexion_revisor", erro)

    modelo_reg = mod_analise if mod_analise == mod_texto else f"{mod_analise} + {mod_texto}"
    return {
        "iteracao_reflexion": nova_iteracao,
        "analise_elegibilidade": analise_dump,
        "resposta_final": _garantir_aviso_institucional(texto_rev),
        "modelos_utilizados": _registrar_modelo(state, chave_agente, modelo_reg),
        "status_api": STATUS_SUCESSO,
    }


def agente_fallback_rag(state: EstadoSistema) -> dict:
    """Sintetiza resposta determinística ancorada exclusivamente nas fichas oficiais recuperadas (Camada 4)."""
    texto = compor_resposta_deterministica_rag(
        documentos=state.get("documentos_encontrados") or [],
        analise_elegibilidade=state.get("analise_elegibilidade"),
        aviso_institucional=AVISO_INSTITUCIONAL,
    )
    return {
        "resposta_final": _garantir_aviso_institucional(texto),
        "modo_degradado": True,
        "modelos_utilizados": _registrar_modelo(state, "fallback_rag", "deterministico_rag_oficial"),
        "status_api": STATUS_DEGRADADO,
    }


def consolidar_encaminhamento_ajuda(state: EstadoSistema) -> dict:
    """Consolida resposta_beneficios, mensagem_apoio e resposta_final antes do encerramento em END."""
    categoria = state.get("categoria_encaminhamento")
    dentro_escopo = bool(state.get("dentro_do_escopo"))
    status_atual = state.get("status_api")
    resposta_atual = (state.get("resposta_final") or "").strip()
    status_atendido = status_atual in (STATUS_SUCESSO, STATUS_DEGRADADO)

    if not categoria:
        if dentro_escopo and status_atendido:
            return {
                "resposta_beneficios": resposta_atual,
                "mensagem_apoio": None,
            }
        return {
            "resposta_beneficios": None,
            "mensagem_apoio": None,
        }

    apoio = state.get("mensagem_apoio") or _montar_resposta_encaminhamento(categoria, state["mensagem_usuario"])

    if not dentro_escopo:
        return {
            "resposta_beneficios": None,
            "mensagem_apoio": apoio,
            "resposta_final": apoio,
            "status_api": STATUS_ENCAMINHAMENTO_AJUDA,
        }

    if status_atendido and resposta_atual:
        combinada = (
            f"{resposta_atual}{SEPARADOR_MENSAGEM_APOIO}{apoio}"
            if apoio not in resposta_atual
            else resposta_atual
        )
        status_final = (
            STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA
            if status_atual == STATUS_DEGRADADO
            else STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA
        )
        return {
            "resposta_beneficios": resposta_atual,
            "mensagem_apoio": apoio,
            "resposta_final": combinada,
            "status_api": status_final,
        }

    combinada_erro = f"{resposta_atual}{SEPARADOR_MENSAGEM_APOIO}{apoio}" if resposta_atual else apoio
    return {
        "resposta_beneficios": None,
        "mensagem_apoio": apoio,
        "resposta_final": combinada_erro,
    }
