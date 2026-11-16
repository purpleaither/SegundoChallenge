"""Ponto de entrada CLI do Assistente Socioassistencial Multiagente (5 nós em LangGraph)."""

import argparse
import json
from pathlib import Path
import re
import sys

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))

from graph import executar_fluxo
from schemas import EstadoSistema


def _resumir_documentos(documentos: list[str] | None) -> list[str]:
    """Extrai cabeçalho resumido (documento, similaridade, programa e órgão) de cada ficha recuperada."""
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


def exibir_debug(estado: EstadoSistema) -> None:
    """Exibe o estado intermediário produzido por cada um dos 5 agentes do grafo."""
    sep = "=" * 76
    print(f"\n{sep}")
    print("DEBUG DO PIPELINE MULTIAGENTE (5 AGENTES — LANGGRAPH)")
    print(sep)
    print(f"Mensagem do usuário : {estado.get('mensagem_usuario')}")
    print(f"Status da API       : {estado.get('status_api')}")

    print(f"\n[1] AGENTE GUARDRAIL")
    print(f"    dentro_do_escopo : {estado.get('dentro_do_escopo')}")
    if estado.get("motivo_rejeicao"):
        print(f"    motivo_rejeicao  : {estado.get('motivo_rejeicao')}")

    if not estado.get("dentro_do_escopo"):
        print("\n    -> Fluxo encerrado no Guardrail (END).")
        print(sep)
        return

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

    print(f"\n[5] AGENTE COMUNICADOR -> resposta_final gerada ({len(estado.get('resposta_final', ''))} caracteres)")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa o Assistente Socioassistencial Multiagente (5 nós em LangGraph)."
    )
    parser.add_argument(
        "mensagem",
        nargs="*",
        help="Relato ou dúvida do cidadão (se omitido, solicita via terminal).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Exibe a saída intermediária de cada um dos 5 agentes.",
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

    print("\nRESPOSTA AO CIDADÃO:\n")
    print(estado_final.get("resposta_final", ""))


if __name__ == "__main__":
    main()
