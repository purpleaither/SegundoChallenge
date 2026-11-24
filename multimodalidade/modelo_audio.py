"""Modelo multimodal de áudio para macOS e navegador.

A entrada falada é convertida em texto pela Web Speech API no Front-end.
Depois o texto entra no mesmo ModeloTexto usado pelo modo textual, garantindo
uma única política de recuperação e resposta. Esta classe também permite que o
macOS leia a resposta em voz alta com a ferramenta nativa `say`.
"""

from __future__ import annotations

import shutil
import subprocess

from modelo_texto import ModeloTexto, RespostaTexto


class ModeloAudio:
    """Entrada: transcrição de áudio; saída: resposta textual + síntese opcional."""

    def __init__(self) -> None:
        self.texto = ModeloTexto()

    def processar(self, transcricao: str) -> RespostaTexto:
        transcricao_limpa = " ".join(transcricao.strip().split())
        if not transcricao_limpa:
            raise ValueError("Não foi recebida uma transcrição de áudio.")

        resultado = self.texto.processar(transcricao_limpa)
        return RespostaTexto(
            modalidade="audio",
            pergunta=resultado.pergunta,
            resposta=resultado.resposta,
            citacoes=resultado.citacoes,
        )

    def falar_resposta(self, resposta: str) -> bool:
        """Sintetiza no macOS usando `say`; retorna False fora do macOS."""
        if not shutil.which("say"):
            return False
        subprocess.run(["say", "-v", "Luciana", "-r", "180", resposta], check=False)
        return True
