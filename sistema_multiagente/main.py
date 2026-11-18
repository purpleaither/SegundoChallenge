"""Ponto de entrada CLI do Assistente Socioassistencial Multiagente (Padrão, ReWOO e Reflexion)."""

import argparse
import json
from pathlib import Path
import re
import sys

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))

from config import TIER_POR_AGENTE
from graph import executar_fluxo
from schemas import (
    STATUS_ENCAMINHAMENTO_AJUDA,
    STATUS_ERRO_API,
    STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA,
    EstadoSistema,
)


def _resumir_documentos(documentos: list[str] | None) -> list[str]:
    """Extrai cabeçalho resumido (programa, órgão e similaridade) de cada ficha recuperada."""
    if not documentos:
        return []
    resumos = []
    for doc in documentos:
        linhas = doc.splitlines()
        cabecalho = linhas[0] if linhas else ""
        programa = next((l.split(": ", 1)[1] for l in linhas if l.startswith("Programa oficial: ")), "?")
        orgao = next((l.split(": ", 1)[1] for l in linhas if l.startswith("Órgão responsável: ")), "?")
        m_sim = re.search(r"similaridade:\s*([0-9.]+)", cabecalho)
        score = m_sim.group(1) if m_sim else "-"
        resumos.append(f"{programa} ({orgao}) | similaridade={score}")
    return resumos


def _resolver_tier_exibicao(chave_agente: str) -> str:
    agente_base = re.sub(r"_\d+$", "", chave_agente)
    return TIER_POR_AGENTE.get(agente_base, "deterministico/rag")


def _rotulo_cabecalho_debug(estado: EstadoSistema) -> str:
    """Resolve o rótulo de exibição no cabeçalho do modo --debug distinguindo encaminhamento de bloqueio."""
    padrao = estado.get("padrao_execucao")
    tem_apoio = bool(estado.get("categoria_encaminhamento"))
    if padrao:
        if tem_apoio:
            return f"{padrao.upper()} + ENCAMINHAMENTO DE AJUDA"
        return padrao.upper()
    status_api = estado.get("status_api")
    if status_api == STATUS_ENCAMINHAMENTO_AJUDA:
        return "ENCAMINHAMENTO DE AJUDA"
    if status_api == STATUS_ERRO_API:
        return "ERRO DE API"
    return "BLOQUEADO"


def exibir_debug(estado: EstadoSistema) -> None:
    """Exibe o padrão selecionado, os modelos escalados e o trace intermediário do caminho executado."""
    sep = "=" * 82
    padrao = estado.get("padrao_execucao")
    status_api = estado.get("status_api")
    eh_encaminhamento = bool(estado.get("categoria_encaminhamento")) or status_api in (
        STATUS_ENCAMINHAMENTO_AJUDA,
        STATUS_SUCESSO_COM_ENCAMINHAMENTO_AJUDA,
    )
    rotulo_cabecalho = _rotulo_cabecalho_debug(estado)

    print(f"\n{sep}")
    print(f"DEBUG DO PIPELINE MULTIAGENTE — LANGGRAPH (PADRÃO: {rotulo_cabecalho})")
    print(sep)
    print(f"Mensagem do usuário : {estado.get('mensagem_usuario')}")
    print(f"Status da API       : {status_api}")

    modelos = estado.get("modelos_utilizados") or {}
    if modelos:
        print("\n[MODELOS ESCALADOS NA EXECUÇÃO]")
        for ag, mod in modelos.items():
            tier = _resolver_tier_exibicao(ag)
            print(f"    - {ag:24s} -> {mod} (tier: {tier})")

    print(f"\n[1] AGENTE GUARDRAIL + SELETOR DE PADRÃO")
    print(f"    dentro_do_escopo         : {estado.get('dentro_do_escopo')}")
    print(f"    padrao_execucao          : {padrao}")
    if estado.get("justificativa_padrao"):
        print(f"    justificativa_padrao     : {estado.get('justificativa_padrao')}")
    if estado.get("categoria_encaminhamento"):
        print(f"    categoria_encaminhamento : {estado.get('categoria_encaminhamento')}")
        if estado.get("dentro_do_escopo"):
            print("    acao_apoio_adicional     : Mensagem de apoio ativada em paralelo à orientação de benefícios.")
    if estado.get("motivo_rejeicao"):
        rotulo_motivo = (
            "motivo_encaminhamento"
            if (eh_encaminhamento and status_api != STATUS_ERRO_API)
            else "motivo_rejeicao"
        )
        print(f"    {rotulo_motivo:24s} : {estado.get('motivo_rejeicao')}")

    if not estado.get("dentro_do_escopo"):
        if eh_encaminhamento:
            print("\n    -> Fluxo encerrado no Guardrail com encaminhamento assistido à rede de ajuda/proteção (END).")
        else:
            print("\n    -> Fluxo encerrado no Guardrail (END).")
        print(sep)
        return

    if padrao == "rewoo":
        print(f"\n[2] AGENTE ReWOO PLANNER (Perfil + Decomposição de Subconsultas)")
        print("    Perfil socioeconômico extraído:")
        print(json.dumps(estado.get("perfil_extraido"), ensure_ascii=False, indent=4))
        passos = estado.get("plano_rewoo") or []
        print(f"    Plano de evidências ({len(passos)} passos):")
        for p in passos:
            print(
                f"      {p.get('id_evidencia')}: [{p.get('foco_necessidade')}] -> query='{p.get('query_busca')}'"
            )

        print(f"\n[3] AGENTE ReWOO WORKER (Busca em Lote no ChromaDB — sem LLM)")
        evidencias = estado.get("evidencias_rewoo") or {}
        for id_ev, docs_ev in evidencias.items():
            res_ev = _resumir_documentos(docs_ev)
            texto_ev = "; ".join(res_ev) if res_ev else "Nenhum documento acima do limiar"
            print(f"    {id_ev} -> {texto_ev}")

        resumos_totais = _resumir_documentos(estado.get("documentos_encontrados"))
        print(f"    Catálogo consolidado deduplicado ({len(resumos_totais)} programas):")
        for idx, item in enumerate(resumos_totais, 1):
            print(f"      {idx}. {item}")

        print(f"\n[4] AGENTE ReWOO SOLVER (Análise RIA02 + Resposta Integrada)")
        print(json.dumps(estado.get("analise_elegibilidade"), ensure_ascii=False, indent=4))
        print(
            f"\n    -> resposta_final consolidada pelo Solver ({len(estado.get('resposta_final', ''))} caracteres)"
        )
        print(sep)
        return

    # Caminho 'padrao' e base do 'reflexion'
    print(f"\n[2] AGENTE EXTRATOR DE PERFIL")
    print(json.dumps(estado.get("perfil_extraido"), ensure_ascii=False, indent=4))

    print(f"\n[3] AGENTE RETRIEVER (ChromaDB)")
    print(f"    query_busca      : {estado.get('query_busca')}")
    resumos = _resumir_documentos(estado.get("documentos_encontrados"))
    print(f"    programas ({len(resumos)})    :")
    for idx, item in enumerate(resumos, 1):
        print(f"      {idx}. {item}")

    print(f"\n[4] AGENTE ANALISTA DE ELEGIBILIDADE")
    print(json.dumps(estado.get("analise_elegibilidade"), ensure_ascii=False, indent=4))

    print(f"\n[5] AGENTE COMUNICADOR -> rascunho/resposta gerada ({len(estado.get('resposta_final', ''))} caracteres)")

    if padrao == "reflexion":
        historico = estado.get("historico_reflexion") or []
        print(
            f"\n[6] CICLO REFLEXION (CRÍTICO <-> REVISOR | revisões aplicadas: {estado.get('iteracao_reflexion', 0)})"
        )
        for item in historico:
            it = item.get("iteracao")
            aprov = item.get("aprovado")
            mod_c = item.get("modelo_critico")
            print(f"    - Auditoria Iteração {it} (modelo={mod_c}): aprovado={aprov}")
            for prob in item.get("problemas_encontrados") or []:
                print(f"        * Problema: {prob}")
            if item.get("instrucoes_correcao"):
                print(f"        * Instrução ao Revisor: {item.get('instrucoes_correcao')}")

    print(sep)


def exibir_resposta_cidadao(estado_final: EstadoSistema) -> None:
    """Imprime a orientação ao cidadão, separando benefícios e mensagem adicional de apoio quando ambas existem."""
    resposta_beneficios = estado_final.get("resposta_beneficios")
    mensagem_apoio = estado_final.get("mensagem_apoio")
    if resposta_beneficios and mensagem_apoio:
        sep = "=" * 82
        print("\nRESPOSTA AO CIDADÃO (PROGRAMAS E BENEFÍCIOS SOCIAIS):\n")
        print(resposta_beneficios)
        print(f"\n{sep}")
        print("MENSAGEM ADICIONAL DE APOIO E CANAIS OFICIAIS DE AJUDA:")
        print(f"{sep}\n")
        print(mensagem_apoio)
        return

    print("\nRESPOSTA AO CIDADÃO:\n")
    print(estado_final.get("resposta_final", ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa o Assistente Socioassistencial Multiagente (Padrão, ReWOO e Reflexion em LangGraph)."
    )
    parser.add_argument(
        "mensagem",
        nargs="*",
        help="Relato ou dúvida do cidadão (se omitido, solicita via terminal).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Exibe o padrão selecionado, os modelos escalados e o trace intermediário de cada agente.",
    )
    args = parser.parse_args()

    mensagem = " ".join(args.mensagem).strip()
    if not mensagem:
        try:
            mensagem = input("Digite sua dúvida ou conte sua situação: ").strip()
        except EOFError:
            mensagem = ""

    if not mensagem:
        print("Nenhuma mensagem informada. Encerrando.", file=sys.stderr)
        sys.exit(1)

    estado_final = executar_fluxo(mensagem)

    if args.debug:
        exibir_debug(estado_final)

    exibir_resposta_cidadao(estado_final)


if __name__ == "__main__":
    main()