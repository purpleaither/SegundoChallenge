"""Avalia a recuperação: o programa esperado aparece entre os TOP_K programas retornados?"""

from buscar import TOP_K, abrir_colecao, buscar_programas

# (pergunta em linguagem popular, trecho do nome do programa esperado)
DENTRO_DO_ESCOPO = [
    ("Estou desempregada e tenho três filhos, tenho direito a algum auxílio?", "Bolsa Família"),
    ("tem ajuda para comprar o botijão de gás?", "Auxílio Gás"),
    ("minha conta de luz tá muito cara, tem desconto?", "Tarifa Social de Energia"),
    ("tem desconto na conta de água?", "Tarifa Social de Água"),
    ("minha mãe é idosa e não tem renda nenhuma", "BPC"),
    ("meu filho é deficiente, tem algum benefício?", "BPC"),
    ("quero fazer faculdade mas não tenho dinheiro", "FIES Social"),
    ("como faço pra não pagar a inscrição do enem?", "Enem"),
    ("tem isenção pra taxa de concurso?", "concursos públicos"),
    ("meu filho tá no ensino médio, tem alguma ajuda?", "Pé-de-Meia"),
    ("quero comprar uma casa, tem programa do governo?", "Minha Casa"),
    ("preciso de remédio de graça", "Farmácia Popular"),
    ("onde consigo absorvente de graça?", "Dignidade Menstrual"),
    ("moro na roça e falta água por causa da seca", "Cisternas"),
    ("sou dona de casa, posso pagar o INSS mais barato?", "Facultativo de Baixa Renda"),
    ("deficiente pode viajar de ônibus de graça pra outro estado?", "Passe Livre"),
    ("quero abrir um negócio pequeno, tem microcrédito?", "Acredita"),
    ("preciso de internet pro meu filho estudar", "Internet Brasil"),
    ("tem cesta de comida pra família passando fome?", "Distribuição de Alimentos"),
    ("estou grávida, tem acompanhamento pro bebê?", "Primeira Infância"),
    ("quais benefícios posso ter como mãe solteira de baixa renda?", "Bolsa Família"),
]

FORA_DO_ESCOPO = [
    "qual o melhor time de futebol do brasil?",
    "como faço bolo de cenoura?",
    "qual a previsão do tempo pra amanhã?",
    "me recomenda um filme de terror",
    "qual a capital da França?",
    "como trocar o pneu de uma bicicleta?",
    "escreva um poema sobre o mar",
    "como fazer arroz soltinho?",
]


def main():
    colecao = abrir_colecao()
    acertos, menor_dentro = 0, 1.0
    print(f"== Dentro do escopo (acerto@{TOP_K}) ==")
    for pergunta, esperado in DENTRO_DO_ESCOPO:
        resultados = buscar_programas(colecao, pergunta)
        programas = [r["meta"]["programa"] for r in resultados]
        ok = any(esperado.lower() in p.lower() for p in programas)
        acertos += ok
        menor_dentro = min(menor_dentro, resultados[0]["similaridade"])
        print(f"{'OK  ' if ok else 'ERRO'} [{resultados[0]['similaridade']:.2f}] {pergunta}\n      -> {programas}")

    maior_fora = 0.0
    print("\n== Fora do escopo (só o score do melhor trecho) ==")
    for pergunta in FORA_DO_ESCOPO:
        s = buscar_programas(colecao, pergunta)[0]["similaridade"]
        maior_fora = max(maior_fora, s)
        print(f"[{s:.2f}] {pergunta}")

    print("\n== Resumo ==")
    print(f"Acerto@{TOP_K}: {acertos}/{len(DENTRO_DO_ESCOPO)} ({acertos / len(DENTRO_DO_ESCOPO):.0%})")
    print(f"Menor score dentro do escopo: {menor_dentro:.2f} | maior score fora: {maior_fora:.2f}")


if __name__ == "__main__":
    main()
