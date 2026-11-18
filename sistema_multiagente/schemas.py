from typing import TypedDict, List, Literal, Optional
from pydantic import BaseModel, Field

PadraoExecucao = Literal["padrao", "rewoo", "reflexion"]


class EstadoSistema(TypedDict):
    mensagem_usuario: str
    dentro_do_escopo: bool
    motivo_rejeicao: Optional[str]
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
    resposta_final: str
    status_api: str


# Agente 1 — Guardrail + Seletor de Padrão (RIA07 / P02)
class ValidacaoEscopo(BaseModel):
    eh_valido: bool = Field(
        description=(
            "True APENAS se o usuário estiver relatando situação socioeconômica, familiar, de vulnerabilidade, "
            "saúde, moradia, educação, trabalho/renda, zona rural ou tirando dúvidas informativas sobre "
            "programas/benefícios sociais. False para assuntos alheios (receitas, esportes, piadas, programação, "
            "curiosidades) OU para pedidos operacionais vedados (consultar CPF/CadÚnico, verificar aprovação "
            "de benefício, fazer cadastro pelo chat)."
        )
    )
    motivo: str = Field(description="Breve justificativa da decisão de escopo.")
    tipo_bloqueio: Optional[Literal["fora_de_escopo", "operacao_proibida_cpf_cadastro"]] = Field(
        default=None,
        description="Preencher somente quando eh_valido=False; None quando a mensagem é válida.",
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
