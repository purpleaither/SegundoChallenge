from typing import TypedDict, List, Literal, Optional
from pydantic import BaseModel, Field


class EstadoSistema(TypedDict):
    mensagem_usuario: str
    dentro_do_escopo: bool
    motivo_rejeicao: Optional[str]
    perfil_extraido: Optional[dict]
    query_busca: Optional[str]
    documentos_encontrados: Optional[List[str]]
    analise_elegibilidade: Optional[dict]
    resposta_final: str
    status_api: str


# Agente 1 — Guardrail (RIA07 / P02)
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
    motivo: str = Field(description="Breve justificativa da decisão.")
    tipo_bloqueio: Optional[Literal["fora_de_escopo", "operacao_proibida_cpf_cadastro"]] = Field(
        default=None,
        description="Preencher somente quando eh_valido=False; None quando a mensagem é válida.",
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