"""Workflow local: preparar casos, coletar respostas e avaliar evidências com RAGAS."""

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def ler_jsonl(caminho):
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def gravar_jsonl(caminho, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        for linha in linhas:
            arquivo.write(json.dumps(linha, ensure_ascii=False, allow_nan=False) + "\n")


def preparar(args):
    from avaliar import DENTRO_DO_ESCOPO, FORA_DO_ESCOPO

    casos = [
        {"id": f"dentro-{i}", "user_input": pergunta, "escopo": True,
         "programa_esperado": esperado, "reference": None}
        for i, (pergunta, esperado) in enumerate(DENTRO_DO_ESCOPO, 1)
    ]
    casos += [{"id": f"fora-{i}", "user_input": pergunta, "escopo": False,
               "reference": None} for i, pergunta in enumerate(FORA_DO_ESCOPO, 1)]
    # Não sobrescreve referências já revisadas pelo grupo.
    if args.casos.exists():
        raise ValueError(f"Arquivo já existe: {args.casos}")
    gravar_jsonl(args.casos, casos)
    print(f"{len(casos)} casos em {args.casos}. Preencha reference com respostas revisadas, se disponíveis.")


def coletar(args):
    from buscar import abrir_colecao
    from comparar import detectar_modelo, montar_contextos, responder_rag, verificar_abstencao

    casos = ler_jsonl(args.casos)
    if args.limite:
        casos = casos[:args.limite]
    modelo = detectar_modelo(args.modelo, args.url)
    colecao = abrir_colecao()
    args.amostras.parent.mkdir(parents=True, exist_ok=True)
    with args.amostras.open("w", encoding="utf-8") as arquivo:
        for caso in casos:
            print(f"Gerando {caso['id']}...", flush=True)
            resposta, programas, duracao = responder_rag(
                caso["user_input"], colecao=colecao, modelo=modelo, url_base=args.url,
            )
            linha = dict(caso, response=resposta, retrieved_contexts=montar_contextos(programas),
                         modelo_gerador=modelo, duracao_s=duracao,
                         coletado_em=datetime.now(timezone.utc).isoformat(),
                         programas=[p["meta"]["programa"] for p in programas])
            if caso["escopo"]:
                esperado = caso.get("programa_esperado", "")
                linha["acerto_top_k"] = (
                    any(esperado.casefold() in p.casefold() for p in linha["programas"])
                    if esperado else None
                )
            else:
                linha["abstencao_heuristica"] = verificar_abstencao(resposta)
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
            arquivo.flush()
    print(f"Amostras salvas em {args.amostras}")


async def avaliar(args):
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import ContextPrecision, ContextRecall, ContextUtilization, Faithfulness

    amostras = ler_jsonl(args.amostras)
    if not amostras:
        raise ValueError("Nenhuma amostra para avaliar.")
    args.saida.mkdir(parents=True, exist_ok=True)
    anteriores = {}
    if args.retomar:
        anteriores = {r["id"]: r for r in ler_jsonl(args.saida / "resultados.jsonl")}
        ids = {a["id"] for a in amostras}
        if not set(anteriores).issubset(ids):
            raise ValueError("Resultados anteriores contêm casos ausentes nas amostras.")
        for amostra in amostras:
            anterior = anteriores.get(amostra["id"])
            if anterior and (anterior.get("modelo_juiz") != args.juiz or any(
                anterior.get(chave) != valor for chave, valor in amostra.items()
            )):
                raise ValueError(f"Amostra ou juiz mudou em {amostra['id']}; use outra pasta de saída.")
    resultados = []
    nomes = ["faithfulness", "context_utilization", "context_precision", "context_recall"]
    async with AsyncOpenAI(base_url=args.url.rstrip("/") + "/v1", api_key="ollama", timeout=180) as cliente:
        juiz = llm_factory(args.juiz, client=cliente, temperature=0, max_tokens=args.max_tokens)
        metricas = {"faithfulness": Faithfulness(llm=juiz),
                    "context_utilization": ContextUtilization(llm=juiz),
                    "context_precision": ContextPrecision(llm=juiz),
                    "context_recall": ContextRecall(llm=juiz)}
        for indice, amostra in enumerate(amostras):
            print(f"Avaliando {amostra['id']}...", flush=True)
            linha = dict(amostra, modelo_juiz=args.juiz, erros={},
                         **{nome: None for nome in nomes})
            anterior = anteriores.get(amostra["id"], {})
            linha["max_tokens_por_metrica"] = dict(anterior.get("max_tokens_por_metrica", {}))
            if amostra["escopo"]:
                for nome, metrica in metricas.items():
                    nota_anterior = anterior.get(nome)
                    if (isinstance(nota_anterior, (float, int))
                            and math.isfinite(nota_anterior) and nome not in anterior.get("erros", {})):
                        linha[nome] = nota_anterior
                        continue
                    if nome in ("context_precision", "context_recall"):
                        if not (amostra.get("reference") or "").strip():
                            continue
                        entrada = {k: amostra[k] for k in ("user_input", "retrieved_contexts", "reference")}
                    else:
                        entrada = {k: amostra[k] for k in ("user_input", "response", "retrieved_contexts")}
                    try:
                        print(f"  {nome}...", flush=True)
                        linha["max_tokens_por_metrica"][nome] = args.max_tokens
                        valor = float((await metrica.ascore(**entrada)).value)
                        if not math.isfinite(valor):
                            raise ValueError("Métrica retornou valor não finito")
                        linha[nome] = valor
                        print(f"  {nome}: {valor:.4f}", flush=True)
                    except Exception as exc:
                        linha["erros"][nome] = str(exc)
                        print(f"  {nome}: falha ({exc})", flush=True)
            resultados.append(linha)
            # Preserva também notas de casos ainda não revisitados nesta retomada.
            pendentes = [anteriores[a["id"]] for a in amostras[indice + 1:] if a["id"] in anteriores]
            gravar_jsonl(args.saida / "resultados.jsonl", resultados + pendentes)

    resumo = {"modelo_juiz": args.juiz, "amostras": len(resultados), "metricas": {}}
    for nome in nomes:
        valores = [r[nome] for r in resultados if r[nome] is not None]
        resumo["metricas"][nome] = {"media": sum(valores) / len(valores) if valores else None,
                                    "avaliadas": len(valores),
                                    "falhas": sum(nome in r["erros"] for r in resultados)}
    for campo in ("acerto_top_k", "abstencao_heuristica"):
        valores = [r[campo] for r in resultados if r.get(campo) is not None]
        resumo[campo] = {"taxa": sum(valores) / len(valores) if valores else None, "casos": len(valores)}
    (args.saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.saida / "metricas.csv").open("w", encoding="utf-8", newline="") as arquivo:
        campos = ["id", "user_input", "escopo", *nomes, "acerto_top_k", "abstencao_heuristica", "erros"]
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore", lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(resultados)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    if any(r["erros"] for r in resultados):
        raise RuntimeError(f"Há métricas com falha. Consulte {args.saida / 'resultados.jsonl'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etapa", choices=["preparar", "coletar", "avaliar"])
    parser.add_argument("--casos", type=Path, default=Path("avaliacao/casos.jsonl"))
    parser.add_argument("--amostras", type=Path, default=Path("avaliacao/amostras.jsonl"))
    parser.add_argument("--saida", type=Path, default=Path("avaliacao/resultados"))
    parser.add_argument("--modelo", help="Modelo gerador instalado no Ollama")
    parser.add_argument("--juiz", help="Modelo avaliador instalado no Ollama")
    parser.add_argument("--url", default="http://localhost:11434")
    parser.add_argument("--limite", type=int)
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Limite de tokens da saída do juiz (padrão: 4096)")
    parser.add_argument("--retomar", action="store_true",
                        help="Reutiliza notas válidas da mesma pasta e repete métricas com falha ou ausentes")
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite deve ser positivo")
    if args.max_tokens < 1:
        parser.error("--max-tokens deve ser positivo")
    if args.etapa == "avaliar" and not args.juiz:
        parser.error("informe --juiz para identificar explicitamente o modelo avaliador")
    try:
        if args.etapa == "preparar":
            preparar(args)
        elif args.etapa == "coletar":
            coletar(args)
        else:
            asyncio.run(avaliar(args))
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(1, f"Erro: {exc}\n")


if __name__ == "__main__":
    main()
