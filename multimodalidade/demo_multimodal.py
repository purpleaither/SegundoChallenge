#!/usr/bin/env python3
"""Demonstração dos dois modelos: texto e áudio."""

from __future__ import annotations

import argparse
import json

from modelo_audio import ModeloAudio
from modelo_texto import ModeloTexto


def imprimir(resultado, falar: bool = False) -> None:
    print(json.dumps(resultado.__dict__, ensure_ascii=False, indent=2))
    if falar:
        ModeloAudio().falar_resposta(resultado.resposta)


def main() -> int:
    parser = argparse.ArgumentParser(description="Demonstração multimodal de texto e áudio")
    parser.add_argument("pergunta", nargs="+", help="Pergunta em português")
    parser.add_argument("--modalidade", choices=("texto", "audio"), default="texto")
    parser.add_argument("--falar", action="store_true", help="Ler a resposta no macOS")
    args = parser.parse_args()

    entrada = " ".join(args.pergunta)
    resultado = (
        ModeloTexto().processar(entrada)
        if args.modalidade == "texto"
        else ModeloAudio().processar(entrada)
    )
    imprimir(resultado, falar=args.falar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
