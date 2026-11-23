from typing import TypedDict, List, Literal, Optional
from pydantic import BaseModel, Field

PadraoExecucao = Literal["padrao", "rewoo", "reflexion"]

STATUS_INICIADO = "iniciado"
STATUS_EM_PROCESSAMENTO = "em_processamento"
STATUS_SUCESSO = "sucesso"
STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA = "sucesso_com_encaminhamento_ajuda"
STATUS_DEGRADADO = "sucesso_degradado"
STATUS_DEGRADADO_COM_ENCAMINHAMENTO_AJUDA = "sucesso_degradado_com_encaminhamento_ajuda"
STATUS_BLOQUEADO = "bloqueado_guardrail"
STATUS_ENCAMINHAMENTO_AJUDA = "encaminhamento_ajuda"
STATUS_ERRO_API = "erro_api"

StatusApi = Literal[
    "iniciado",
    "em_processamento",
    "sucesso",
    "sucesso_com_encaminhamento_ajuda",
    "sucesso_degradado",
    "sucesso_degradado_com_encaminhamento_ajuda",
    "bloqueado_guardrail",
    "encaminhamento_ajuda",
    "erro_api",
]

CategoriaEncaminhamentoAjuda = Literal[
    "autoexterminio",
    "codigo_penal",
    "autoexterminio_e_codigo_penal",
]

TipoIntervencaoGuardrail = Literal[
    "fora_de_escopo",
    "operacao_proibida_cpf_cadastro",
    "sem_escopo_socioeconomico",
    "autoexterminio",
    "codigo_penal",
    "autoexterminio_e_codigo_penal",
]

CATEGORIAS_ENCAMINHAMENTO_AJUDA: tuple[CategoriaEncaminhamentoAjuda, ...] = (
    "autoexterminio",
    "codigo_penal",
    "autoexterminio_e_codigo_penal",
)


class EstadoSistema(TypedDict):
    mensagem_usuario: str
    dentro_do_escopo: bool
    motivo_rejeicao: Optional[str]
    categoria_encaminhamento: Optional[CategoriaEncaminhamentoAjuda]
    padrao_execucao: Optional[PadraoExecucao]
    justificativa_padrao: Optional[str]
    perfil_extraido: Optional[dict]
    query_busca: Optional[str]
    documentos_encontrados: Optional[List[str]]
    plano_rewoo: Optional[List[dict]]
    evidencias_rewoo: Optional[dict]
    analise_elegibilidade: Optional[dict]
    critica_reflexion: Optional[dict]
    iteracao_reflexion: int
    historico_reflexion: Optional[List[dict]]
    modelos_utilizados: Optional[dict]
    modo_degradado: bool
    eventos_fallback: Optional[List[str]]
    resposta_beneficios: Optional[str]
    mensagem_apoio: Optional[str]
    resposta_final: str
    status_api: str


# Agente 1 — Guardrail + Seletor de Padrão (RIA06 / RIA07 / P02)
class ValidacaoEscopo(BaseModel):
    eh_valido: bool = Field(
        description=(
            "True SEMPRE que a mensagem contiver relato de situação socioeconômica, familiar, vulnerabilidade, "
            "saúde, deficiência, moradia, educação, trabalho/desemprego/renda, alimentação, zona rural OU "
            "dúvida informativa legítima sobre programas/benefícios sociais — INCLUSIVE quando também houver "
            "menção a autoextermínio/sofrimento agudo ou vitimização/ocorrência penal na mesma mensagem "
            "(ex.: 'sou mãe solteira, 3 filhos, desempregada, quero morrer' -> eh_valido=True). "
            "False APENAS quando NÃO houver contexto socioeconômico/dúvida de benefício (ex.: crise ou relato "
            "criminal isolado sem relação socioassistencial), quando for pedido de instrução para fraude/ilícito "
            "('como falsificar documento'), pedido operacional vedado por P02 (consultar CPF/CadÚnico, fazer "
            "cadastro pelo chat) ou assunto fora de escopo (receitas, esportes, piadas, programação)."
        )
    )
    motivo: str = Field(description="Breve justificativa objetiva, em português, da decisão do Guardrail.")
    categoria_encaminhamento: Optional[CategoriaEncaminhamentoAjuda] = Field(
        default=None,
        description=(
            "Avaliado de forma INDEPENDENTE de eh_valido (pode ser preenchido tanto com eh_valido=True quanto False). "
            "Preencha 'autoexterminio' para ideação suicida, intenção de tirar a própria vida ou automutilação/autolesão; "
            "'codigo_penal' para elementos que ferem o Código Penal (violência doméstica/familiar, agressão, ameaça, "
            "abuso/exploração, cárcere privado, trabalho escravo, furto/roubo/extorsão, retenção de documentos/cartão, "
            "fraude/falsificação/ilícito penal); "
            "'autoexterminio_e_codigo_penal' quando ambos ocorrerem juntos. "
            "Deixe None quando não houver risco real nem matéria penal (metáforas como 'a conta de luz está me matando', "
            "'morrendo de preocupação' ou 'cortaram meu Bolsa Família' devem ficar com categoria_encaminhamento=None)."
        ),
    )
    tipo_bloqueio: Optional[TipoIntervencaoGuardrail] = Field(
        default=None,
        description=(
            "Preencher SOMENTE quando eh_valido=False (deixe None quando eh_valido=True). "
            "Valores quando eh_valido=False: 'fora_de_escopo' (assuntos alheios como receitas, esportes, piadas), "
            "'operacao_proibida_cpf_cadastro' (consulta de CPF/CadÚnico, aprovação ou cadastro pelo chat) ou "
            "'sem_escopo_socioeconomico' (quando houver apenas crise/crime isolado ou pedido de fraude sem relato "
            "socioeconômico válido para análise de benefícios)."
        ),
    )
    padrao_execucao: Optional[PadraoExecucao] = Field(
        default=None,
        description=(
            "Obrigatório quando eh_valido=True; None quando eh_valido=False. "
            "Use 'padrao' para dúvidas diretas sobre um único benefício ou relatos simples; "
            "'rewoo' para relatos multifacetados com múltiplas vulnerabilidades distintas ou perguntas comparativas/amplas; "
            "'reflexion' para casos limítrofes/ambíguos, potenciais conflitos/acumulação de benefícios ou exigência explícita de detalhamento legal/normativo (2024-2026)."
        ),
    )
    justificativa_padrao: Optional[str] = Field(
        default=None,
        description="Explicação objetiva em uma frase sobre o porquê da escolha do padrão quando eh_valido=True.",
    )


# Agente 2 — Extrator de Perfil (RIA01)
class PerfilSocioeconomico(BaseModel):
    resumo_situacao: str = Field(description="Resumo objetivo, em uma ou duas frases, da situação relatada.")
    faixa_renda_familiar_ou_per_capita: Optional[str] = Field(
        default=None, description="Renda declarada (ex.: 'sem renda', 'meio salário mínimo'). None se não informada."
    )
    situacao_trabalho: Optional[str] = Field(
        default=None,
        description="Ex.: desempregado, informal, agricultor familiar, MEI, dona de casa. None se não informada.",
    )
    composicao_familiar: List[str] = Field(
        default_factory=list,
        description="Ex.: '3 filhos/crianças', 'gestante', 'idoso na família'. Lista vazia se não informada.",
    )
    condicoes_especificas: List[str] = Field(
        default_factory=list,
        description=(
            "Ex.: pessoa com deficiência, idoso 65+, estudante, inscrito no CadÚnico, falta de água/seca, "
            "zona rural, necessidade de medicamentos, conta de luz/gás alta, moradia/aluguel."
        ),
    )
    palavras_chave_busca: List[str] = Field(
        default_factory=list,
        description="Termos oficiais e populares combinados para enriquecer a busca na base de benefícios.",
    )


# Agente 4 — Analista de Elegibilidade (RIA02)
StatusElegibilidade = Literal[
    "elegivel", "potencialmente_elegivel", "inelegivel", "criterio_nao_especificado_na_base"
]


class AvaliacaoPrograma(BaseModel):
    nome_programa: str = Field(description="Título oficial do programa, copiado literalmente do documento.")
    orgao_responsavel: str = Field(description="Campo 'Órgão responsável' copiado literalmente do documento.")
    status_elegibilidade: StatusElegibilidade
    criterios_atendidos: List[str] = Field(
        default_factory=list, description="Requisitos do documento que o perfil declarado já atende."
    )
    criterios_pendentes_ou_impeditivos: List[str] = Field(
        default_factory=list,
        description="Requisitos que precisam ser comprovados/confirmados ou que impedem o acesso.",
    )
    base_legal: str = Field(
        description="'Lei base', 'Regulamentação' e 'Atualização recente' copiados literalmente do documento."
    )
    observacoes_documentais: str = Field(
        description=(
            "Lacunas da base (ex.: 'Não especificado no documento de origem', 'Informação parcial no documento') "
            "e observações legais relevantes."
        )
    )


ItemElegibilidade = AvaliacaoPrograma


class AnaliseElegibilidade(BaseModel):
    programas_avaliados: List[AvaliacaoPrograma] = Field(default_factory=list)
    resumo_parecer: str = Field(description="Parecer técnico curto consolidando a análise.")


# Padrão ReWOO (Planner -> Worker -> Solver)
class PassoPlanoReWOO(BaseModel):
    id_evidencia: str = Field(description="Identificador sequencial da evidência, ex.: '#E1', '#E2'.")
    foco_necessidade: str = Field(description="Vulnerabilidade, público ou dúvida específica investigada neste passo.")
    query_busca: str = Field(
        description="Consulta semântica combinando termos populares e técnicos (RIA01) para recuperar fichas no ChromaDB."
    )
    categoria: Optional[str] = Field(default=None, description="Filtro opcional de categoria documental, ou None.")
    esfera: Optional[str] = Field(default=None, description="Filtro opcional de esfera (ex.: 'Federal'), ou None.")


class PlanoReWOO(BaseModel):
    perfil: PerfilSocioeconomico
    passos: List[PassoPlanoReWOO] = Field(
        description="Lista de 2 a 4 passos independentes (#E1, #E2...) cobrindo todas as frentes do relato."
    )


# Padrão Reflexion (Actor -> Crítico -> Revisor)
class AvaliacaoCriticaReflexion(BaseModel):
    aprovado: bool = Field(
        description=(
            "True SOMENTE se a análise e a resposta respeitarem integralmente a ancoragem documental (RIA02), "
            "citarem nome oficial/órgão/legislação sem omissões relevantes e incluírem próximos passos + aviso P02."
        )
    )
    problemas_encontrados: List[str] = Field(
        default_factory=list,
        description="Lista objetiva de alucinações, omissões documentais/legais ou falhas de transparência/P02.",
    )
    instrucoes_correcao: str = Field(
        default="",
        description="Instruções diretas e acionáveis para o Revisor corrigir os problemas (vazio quando aprovado=True).",
    )
