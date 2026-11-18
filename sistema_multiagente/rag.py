"""Integração do sistema multiagente com a base oficial em Dados-RAG (KnowledgeBase / ChromaDB local)."""

import re
import sys
from pathlib import Path
from typing import Optional

import chromadb

PASTA_ATUAL = Path(__file__).resolve().parent
if str(PASTA_ATUAL) not in sys.path:
    sys.path.insert(0, str(PASTA_ATUAL))

PASTA_RAIZ = PASTA_ATUAL.parent
PASTA_DADOS_RAG = PASTA_RAIZ / "Dados-RAG"
if str(PASTA_DADOS_RAG) not in sys.path:
    sys.path.insert(0, str(PASTA_DADOS_RAG))

from schemas import CategoriaEncaminhamentoAjuda

from RAG.dataset import build_program_chunks, read_programs, render_program_document, slug
from RAG.rag import (
    DATASET_VERSION,
    VECTOR_DB_PATH,
    KnowledgeBase,
    ModelUnavailableError,
    expand_question,
)

TOP_K = 4
LIMIAR_SIMILARIDADE = 0.25
PASTA_CHROMA_LOCAL = PASTA_RAIZ / "rag" / "chroma_db"
COLECAO_LOCAL = f"multiagente_{slug(DATASET_VERSION)}"

CAMPOS_PERFIL_BUSCA = (
    "palavras_chave_busca",
    "resumo_situacao",
    "situacao_trabalho",
    "faixa_renda_familiar_ou_per_capita",
    "composicao_familiar",
    "condicoes_especificas",
)

_PROGRAMAS_POR_ID: dict[str, dict[str, str]] | None = None
_COLECAO_FALLBACK = None


def _mapa_programas() -> dict[str, dict[str, str]]:
    """Carrega e indexa em memória os 42 programas oficiais do CSV homologado em Dados-RAG."""
    global _PROGRAMAS_POR_ID
    if _PROGRAMAS_POR_ID is None:
        _PROGRAMAS_POR_ID = {slug(row["programa"]): row for row in read_programs()}
    return _PROGRAMAS_POR_ID


def _abrir_colecao_local():
    """Abre (e indexa automaticamente na 1ª execução) o ChromaDB local sem depender de Ollama externo."""
    global _COLECAO_FALLBACK
    if _COLECAO_FALLBACK is not None:
        return _COLECAO_FALLBACK

    PASTA_CHROMA_LOCAL.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(PASTA_CHROMA_LOCAL))
    col = cliente.get_or_create_collection(
        name=COLECAO_LOCAL,
        metadata={"hnsw:space": "cosine"},
    )
    if col.count() == 0:
        chunks = build_program_chunks(list(_mapa_programas().values()))
        col.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
        )
    _COLECAO_FALLBACK = col
    return _COLECAO_FALLBACK


def _buscar_trechos_brutos(pergunta: str, k: int = TOP_K * 4) -> list[dict]:
    """Consulta KnowledgeBase (bge-m3/Ollama) se disponível; caso contrário, usa o ChromaDB local."""
    mapa = _mapa_programas()

    if VECTOR_DB_PATH.exists():
        kb = None
        try:
            kb = KnowledgeBase(path=VECTOR_DB_PATH)
            resultados_kb = kb.search(pergunta, limit=k)
            if resultados_kb:
                saida = []
                for item in resultados_kb:
                    pid = item.get("program_id") or slug(item.get("program_name", ""))
                    row = mapa.get(pid, {})
                    saida.append(
                        {
                            "texto": item["text"],
                            "similaridade": float(item["similarity"]),
                            "meta": {
                                "arquivo": pid,
                                "programa": row.get("programa") or item.get("program_name", ""),
                                "orgao": row.get("orgao_responsavel") or item.get("agency_id", ""),
                                "esfera": row.get("esfera", "Federal"),
                                "categoria": row.get("categoria", ""),
                                "fonte": row.get("fonte_documental") or item.get("title", ""),
                                "url": row.get("url_fonte") or item.get("url", ""),
                            },
                        }
                    )
                return saida
        except ModelUnavailableError:
            pass
        finally:
            if kb is not None:
                kb.close()

    col = _abrir_colecao_local()
    total = col.count()
    if total == 0:
        return []

    consulta_expandida = expand_question(pergunta)
    r = col.query(query_texts=[consulta_expandida], n_results=min(total, max(k, 4)))
    saida_local = []
    for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        pid = meta.get("program_id", "")
        row = mapa.get(pid, {})
        saida_local.append(
            {
                "texto": doc,
                "similaridade": 1.0 - float(dist),
                "meta": {
                    "arquivo": pid,
                    "programa": row.get("programa") or meta.get("program_name", ""),
                    "orgao": row.get("orgao_responsavel") or meta.get("agency_id", ""),
                    "esfera": row.get("esfera") or meta.get("jurisdiction", "Federal"),
                    "categoria": row.get("categoria", ""),
                    "fonte": row.get("fonte_documental") or meta.get("title", ""),
                    "url": row.get("url_fonte") or meta.get("url", ""),
                },
            }
        )
    return saida_local


def montar_contexto(programas: list[dict]) -> str:
    """Renderiza as fichas completas dos programas recuperados no formato documental estruturado."""
    mapa = _mapa_programas()
    blocos = []
    for i, item in enumerate(programas, 1):
        meta = item["meta"]
        pid = meta["arquivo"]
        row = mapa.get(pid)
        corpo = render_program_document(row).strip() if row else item.get("texto", "").strip()
        blocos.append(
            f"=== DOCUMENTO {i} (similaridade: {item['similaridade']:.2f}) ===\n"
            f"Programa oficial: {meta['programa']}\n"
            f"Órgão responsável: {meta['orgao']}\n"
            f"Esfera: {meta['esfera']} | Categoria: {meta['categoria']}\n"
            f"Fonte documental: {meta['fonte']}\n"
            f"URL oficial: {meta['url']}\n\n"
            f"{corpo}"
        )
    return "\n\n".join(blocos)


_EXPRESSOES_FIGURADAS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:a\s+|as\s+|essa\s+|essas\s+|o\s+|os\s+)?(?:conta(?:s)?(?:\s+de\s+(?:luz|[aá]gua|g[aá]s|energia))?|d[ií]vida(?:s)?|aluguel|boleto(?:s)?|pre[cç]o(?:s)?|infla[cç][aã]o|fome|calor|frio|cansa[cç]o|estresse|preocupa[cç][aã]o|situa[cç][aã]o|desemprego|trabalho|juros)\s+(?:est[aá]|est[aã]o|t[aá]|t[aã]o|vai|v[aã]o|vem|anda|andam)\s+me\s+matando\b",
        r"\b(?:a\s+|as\s+|essa\s+|essas\s+|o\s+|os\s+)?(?:conta(?:s)?(?:\s+de\s+(?:luz|[aá]gua|g[aá]s|energia))?|d[ií]vida(?:s)?|aluguel|boleto(?:s)?|pre[cç]o(?:s)?|infla[cç][aã]o|fome|desemprego|juros)\s+(?:vai|v[aã]o)\s+me\s+matar\b",
        r"\bme\s+matando\s+de\s+(?:trabalhar|estudar|tanto\s+trabalhar|procurar|correr|tentar)\b",
        r"\bme\s+matar\s+de\s+(?:trabalhar|estudar|tanto\s+trabalhar)\b",
        r"\bmatar\s+a\s+(?:fome|sede|saudade)\b",
        r"\bmorrendo\s+de\s+(?:fome|medo|preocupa[cç][aã]o|vergonha|frio|calor|sede|dor|saudade|sono|raiva|ansiedade|vontade|cansad[oa])\b",
        r"\bcortar(?:am)?\s+(?:o\s+|a\s+|os\s+|as\s+|meu\s+|minha\s+|nosso\s+|nossa\s+)?(?:bolsa\s+fam[ií]lia|benef[ií]cio|aux[ií]lio|bpc|aposentadoria|pens[aã]o|luz|energia|[aá]gua|g[aá]s|internet|sal[aá]rio|cadastro|renda)\b",
    )
)

_PADROES_AUTOEXTERMINIO = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:quero|vou|penso\s+em|pensando\s+em|tenho\s+vontade\s+de|vontade\s+de|decidi|planejo|tentando|tentei)\s+(?:me\s+matar|me\s+suicidar|tirar\s+(?:a\s+)?minha\s+(?:pr[oó]pria\s+)?vida|tirar\s+a\s+pr[oó]pria\s+vida|acabar\s+com\s+(?:a\s+)?minha\s+vida|dar\s+fim\s+(?:na|[aà]|a)\s+minha\s+vida|p[oô]r\s+fim\s+(?:na|[aà]|a)\s+minha\s+vida)\b",
        r"\b(?:tirar\s+(?:a\s+)?minha\s+(?:pr[oó]pria\s+)?vida|tirar\s+a\s+pr[oó]pria\s+vida|acabar\s+com\s+(?:a\s+)?minha\s+vida|dar\s+fim\s+(?:na|[aà]|a)\s+minha\s+vida|p[oô]r\s+fim\s+(?:na|[aà]|a)\s+minha\s+vida)\b",
        r"\b(?:cometer|tentar|planejando|pensando\s+em|penso\s+em)\s+suic[ií]dio\b",
        r"\b(?:idea[cç][aã]o\s+suicida|pensamentos?\s+suicidas?|crise\s+suicida|risco\s+de\s+suic[ií]dio|me\s+suicidar)\b",
        r"\bn[aã]o\s+(?:quero|aguento|consigo|suporto)\s+mais\s+viver\b",
        r"\b(?:quero\s+morrer|prefiro\s+morrer|melhor\s+eu\s+morrer|queria\s+estar\s+mort[oa]|quero\s+dormir\s+e\s+n[aã]o\s+acordar)\b",
        r"\b(?:como\s+(?:fa[cç]o\s+(?:para|pra)\s+|posso\s+)?(?:me\s+matar|morrer\s+sem\s+dor)|m[eé]todos?\s+para\s+(?:me\s+matar|morrer|suic[ií]dio))\b",
        r"\b(?:automutila[cç][aã]o|autoles[aã]o|autoexterm[ií]nio|cortar\s+(?:os|meus)\s+pulsos|(?:ando|estou|venho)\s+me\s+(?:cortando|mutilando|ferindo\s+de\s+prop[oó]sito)|(?:quero|vou|vontade\s+de)\s+me\s+(?:cortar|mutilar|enforcar))\b",
        r"\b(?:vou|quero)\s+tomar\s+(?:veneno|chumbinho|todos\s+os\s+rem[eé]dios)\b",
    )
)

_PADROES_CODIGO_PENAL = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bviol[eê]ncia\s+(?:dom[eé]stica|familiar|f[ií]sica|sexual|patrimonial)\b",
        r"\b(?:meu|minha)\s+(?:marido|companheir[oa]|namorad[oa]|ex(?:-marido|-companheir[oa]|-namorad[oa])?|espos[oa]|pai|m[aã]e|padrasto|madrasta|filh[oa]|irm[aã]o?|ti[oa]|patr[aã]o|chefe)\s+(?:me\s+(?:bate|bateu|espanca|espancou|agride|agrediu|amea[cç]a|amea[cç]ou|trancou|tranca|estuprou|violentou|extorque|extorquiu)|est[aá]\s+me\s+(?:batendo|espancando|agredindo|amea[cç]ando)|disse\s+que\s+vai\s+me\s+matar|vai\s+me\s+matar)\b",
        r"\b(?:estou|t[oô]|venho|ando)\s+(?:apanhando|sendo\s+(?:espancad[oa]|agredid[oa]|amea[cç]ad[oa]|extorquid[oa]|mantid[oa]\s+pres[oa]|mantid[oa]\s+trancad[oa]|abusad[oa]|violentad[oa]))\b",
        r"\b(?:apanhando\s+em\s+casa|apanhando\s+do\s+meu\s+(?:marido|companheiro|namorado|ex|pai|padrasto)|amea[cç]a\s+de\s+morte|amea[cç](?:ou|a|ando)\s+me\s+matar|lei\s+maria\s+da\s+penha)\b",
        r"\b(?:c[aá]rcere\s+privado|trabalho\s+escravo|trabalho\s+an[aá]logo\s+[aà]\s+escravid[aã]o|me\s+mant[eé]m\s+trancad[oa]|n[aã]o\s+me\s+deixa\s+sair\s+de\s+casa)\b",
        r"\b(?:ret[eé]m|reteve|prendeu|tomou\s+[aà]\s+for[cç]a|confiscou|roubou|roubaram|furtou|furtaram)\s+(?:meus?\s+documentos?|todos\s+os\s+meus\s+documentos|minha\s+carteira\s+de\s+trabalho|(?:o\s+)?meu\s+cart[aã]o\s+(?:do\s+(?:bolsa\s+fam[ií]lia|bpc|benef[ií]cio|aux[ií]lio)|de\s+benef[ií]cio))\b",
        r"\b(?:abuso\s+sexual|explora[cç][aã]o\s+sexual|explora[cç][aã]o\s+infantil|estupro|fui\s+estuprad[oa]|sofri\s+(?:um\s+)?estupro|fui\s+abusad[oa]|maus[- ]tratos\s+contra\s+(?:crian[cç]a|idos[oa]|vulner[aá]vel|meu\s+filho|minha\s+filha|minha\s+m[aã]e|meu\s+pai))\b",
        r"\b(?:fui\s+assaltad[oa]|sofri\s+(?:um\s+)?assalto|sofri\s+extors[aã]o|v[ií]tima\s+de\s+(?:estelionato|roubo|extors[aã]o|c[aá]rcere))\b",
        r"\b(?:como\s+(?:fa[cç]o\s+(?:para|pra)\s+|posso\s+)?(?:fraudar|burlar|falsificar)|quero\s+(?:fraudar|falsificar))\b",
        r"\b(?:falsificar\s+(?:documento|documentos|comprovante|laudo|atestado|assinatura|receita)|documento\s+falso|laudo\s+falso|atestado\s+falso|usar\s+cpf\s+(?:falso|de\s+outra\s+pessoa|de\s+terceiro)|declarar\s+renda\s+falsa|fraude\s+no\s+(?:bolsa\s+fam[ií]lia|bpc|cad[uú]nico|benef[ií]cio)|fraudar\s+o\s+(?:bolsa\s+fam[ií]lia|bpc|cad[uú]nico))\b",
        r"\b(?:traficar|tr[aá]fico\s+de\s+drogas|vender\s+drogas)\b",
    )
)

_INDICIO_FALLBACK_AUTOEXTERMINIO = re.compile(
    r"\b(?:suic[ií]d\w*|autoexterm\w*|automutil\w*|autoles\w*|me\s+matar|acabar\s+com\s+tudo|desistir\s+de\s+viver|n[aã]o\s+vejo\s+mais\s+sentido\s+em\s+viver)\b",
    re.IGNORECASE,
)

_INDICIO_FALLBACK_CODIGO_PENAL = re.compile(
    r"\b(?:viol[eê]ncia|agress[aã]o|agredid\w*|espanc\w*|apanhand\w*|amea[cç]\w*|abuso|abusad\w*|estupr\w*|c[aá]rcere|ref[eé]m|escrav\w*|roub\w*|assalt\w*|furt\w*|extors\w*|estelionat\w*|falsific\w*|fraud\w*|il[ií]cit\w*|crime|criminos\w*|delegacia|pol[ií]cia)\b",
    re.IGNORECASE,
)


_PADROES_PEDIDO_ILICITO_EXPLICITO = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:como\s+(?:fa[cç]o\s+(?:para|pra)\s+|posso\s+)?(?:fraudar|burlar|falsificar|esconder\s+(?:meu\s+)?sal[aá]rio|omitir\s+renda)|me\s+ensina\s+.*?(?:fraudar|burlar|falsificar|esconder\s+(?:meu\s+)?sal[aá]rio)|quero\s+(?:fraudar|falsificar))\b",
        r"\b(?:falsificar\s+(?:documento|documentos|comprovante|laudo|atestado|assinatura|receita)|documento\s+falso|laudo\s+falso|atestado\s+falso|usar\s+cpf\s+(?:falso|de\s+outra\s+pessoa|de\s+terceiro)|declarar\s+renda\s+falsa|fraude\s+no\s+(?:bolsa\s+fam[ií]lia|bpc|cad[uú]nico|benef[ií]cio)|fraudar\s+o\s+(?:bolsa\s+fam[ií]lia|bpc|cad[uú]nico))\b",
        r"\b(?:traficar|tr[aá]fico\s+de\s+drogas|vender\s+drogas)\b",
    )
)

_PADRAO_CONTEXTO_SOCIOECONOMICO = re.compile(
    r"\b(?:"
    r"m[aã]e\s+solteira|m[aã]e\s+solo|pai\s+solo|filh[oa]s?|crian[cç]as?|beb[eê]s?|gestante|gr[aá]vida|"
    r"idos[oa]s?|aposentad[oa]s?|defici[eê]ncia|pcd|autis(?:mo|ta)|cadeirante|"
    r"desempregad[oa]s?|demitid[oa]s?|perdi\s+(?:o|meu)\s+emprego|sem\s+emprego|sem\s+trabalho|"
    r"sem\s+renda|baixa\s+renda|pouca\s+renda|sem\s+dinheiro|pagar\s+(?:as\s+)?contas|"
    r"sal[aá]rio|informal|bico|aut[oô]nom[oa]|mei\b|dona\s+de\s+casa|"
    r"fome|passando\s+necessidade|dificuldade\s+financeira|d[ií]vidas?|endividad[oa]|"
    r"aluguel|moradia|despej\w*|sem[- ]teto|situa[cç][aã]o\s+de\s+rua|enchente|abrigo|"
    r"conta\s+de\s+(?:luz|[aá]gua|energia|g[aá]s)|botij[aã]o|tarifa\s+social|"
    r"zona\s+rural|ro[cç]a|agricultor\w*|seca|cisterna|"
    r"estudante|ensino\s+m[eé]dio|escola\s+p[uú]blica|p[eé][- ]de[- ]meia|"
    r"rem[eé]dio\s+gratuito|medicamento\s+gratuito|farm[aá]cia\s+popular|"
    r"benef[ií]cios?|aux[ií]lios?|programa\s+social|programas\s+sociais|"
    r"bolsa\s+fam[ií]lia|bpc|loas|cad[uú]nico|cadastro\s+[uú]nico|cras\b|inss\b|minha\s+casa"
    r")\b",
    re.IGNORECASE,
)


def _neutralizar_expressoes_figuradas(pergunta: str) -> str:
    """Remove metáforas coloquiais conhecidas em cópia normalizada para evitar falsos positivos."""
    texto = re.sub(r"\s+", " ", pergunta).strip()
    for padrao in _EXPRESSOES_FIGURADAS:
        texto = padrao.sub(" ", texto)
    return texto


def detectar_situacao_critica_deterministica(pergunta: str) -> Optional[CategoriaEncaminhamentoAjuda]:
    """Detecta com alta precisão expressões explícitas de autoextermínio e/ou matéria penal."""
    texto = _neutralizar_expressoes_figuradas(pergunta)
    tem_autoexterminio = any(p.search(texto) for p in _PADROES_AUTOEXTERMINIO)
    tem_codigo_penal = any(p.search(texto) for p in _PADROES_CODIGO_PENAL)
    if tem_autoexterminio and tem_codigo_penal:
        return "autoexterminio_e_codigo_penal"
    if tem_autoexterminio:
        return "autoexterminio"
    if tem_codigo_penal:
        return "codigo_penal"
    return None


def inferir_categoria_sensivel_fallback(pergunta: str) -> Optional[CategoriaEncaminhamentoAjuda]:
    """Identifica indícios sensíveis mais amplos para roteamento seguro ao LLM ou fallback de filtro SAFETY."""
    explicita = detectar_situacao_critica_deterministica(pergunta)
    if explicita is not None:
        return explicita
    texto = _neutralizar_expressoes_figuradas(pergunta)
    tem_auto = bool(_INDICIO_FALLBACK_AUTOEXTERMINIO.search(texto))
    tem_penal = bool(_INDICIO_FALLBACK_CODIGO_PENAL.search(texto))
    if tem_auto and tem_penal:
        return "autoexterminio_e_codigo_penal"
    if tem_auto:
        return "autoexterminio"
    if tem_penal:
        return "codigo_penal"
    return None


def eh_pedido_ilicito_explicito(pergunta: str) -> bool:
    """Detecta pedidos diretos de instrução ou prática de fraude documental/beneficiária ou tráfico."""
    texto = re.sub(r"\s+", " ", pergunta).strip()
    return any(p.search(texto) for p in _PADROES_PEDIDO_ILICITO_EXPLICITO)


def possui_contexto_socioeconomico(pergunta: str) -> bool:
    """Verifica se a mensagem traz contexto socioeconômico, familiar ou dúvida legítima sobre benefícios."""
    if eh_pedido_ilicito_explicito(pergunta) or violacao_operacional_p02(pergunta):
        return False
    return bool(_PADRAO_CONTEXTO_SOCIOECONOMICO.search(pergunta))


def neutralizar_trechos_criticos_para_extracao(pergunta: str) -> str:
    """Substitui apenas expressões explícitas de autolesão/crime para retry caso o LLM acione filtro SAFETY."""
    texto = pergunta
    for padrao in (*_PADROES_AUTOEXTERMINIO, *_PADROES_CODIGO_PENAL):
        texto = padrao.sub("[relato de vulnerabilidade aguda]", texto)
    texto = _INDICIO_FALLBACK_AUTOEXTERMINIO.sub("[vulnerabilidade aguda]", texto)
    return re.sub(r"\s+", " ", texto).strip()


def violacao_operacional_p02(pergunta: str) -> bool:
    """Detecta pedidos operacionais vedados por P02 (consulta de CPF/CadÚnico, cadastro ou aprovação)."""
    p = pergunta.lower()
    tem_cpf = bool(re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", p)) or "meu cpf" in p
    acao_vedada = any(
        termo in p
        for termo in (
            "consulta aí",
            "consultar meu",
            "consulta meu",
            "consulte",
            "consultar",
            "consulta ",
            "cadunico",
            "cadúnico",
            "faz meu cadastro",
            "fazer meu cadastro",
            "fazer cadastro",
            "faz cadastro",
            "meu cadastro",
            "aprova meu",
            "aprovar",
            "foi aprovado",
            "aprovado",
        )
    )
    return tem_cpf and acao_vedada


def contem_dados_ou_pedido_p02(pergunta: str) -> bool:
    """Verifica se há número de CPF ou pedido operacional P02 na mensagem."""
    p = pergunta.lower()
    tem_cpf_numerico = bool(re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", p))
    return tem_cpf_numerico or violacao_operacional_p02(pergunta)


def consultar_rag(pergunta: str, k: int = TOP_K) -> str:
    """Consulta o banco vetorial e retorna os documentos formatados."""
    por_prog: dict[str, dict] = {}
    for trecho in _buscar_trechos_brutos(pergunta, k=k * 4):
        if trecho["similaridade"] >= LIMIAR_SIMILARIDADE:
            por_prog.setdefault(trecho["meta"]["arquivo"], trecho)
    programas = list(por_prog.values())[:k]
    if not programas:
        return "Nenhum documento relevante encontrado na base."
    return montar_contexto(programas)


def montar_query_enriquecida(mensagem_usuario: str, perfil_extraido: Optional[dict] = None) -> str:
    """Combina o relato com os campos preenchidos do perfil socioeconômico."""
    partes = []
    for campo in CAMPOS_PERFIL_BUSCA:
        valor = (perfil_extraido or {}).get(campo)
        if isinstance(valor, list):
            partes.extend(str(v) for v in valor if v)
        elif valor:
            partes.append(str(valor))
    partes.append(mensagem_usuario)
    return " ".join(dict.fromkeys(p.strip() for p in partes if p and p.strip()))


def _dividir_contexto(contexto: str) -> list[str]:
    """Separa o texto de montar_contexto() em uma ficha por programa ('=== DOCUMENTO N ...')."""
    return [bloco.strip() for bloco in re.split(r"(?m)^(?==== DOCUMENTO \d+)", contexto) if bloco.strip()]


def _buscar_por_consulta(
    consulta: str,
    k_busca: int,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict[str, dict]:
    """Executa uma busca vetorial deduplicada por programa respeitando limiar e filtros opcionais."""
    melhores: dict[str, dict] = {}
    for trecho in _buscar_trechos_brutos(consulta, k=k_busca):
        meta = trecho["meta"]
        if trecho["similaridade"] < limiar_similaridade:
            continue
        if categoria and meta.get("categoria", "").lower() != categoria.lower():
            continue
        if esfera and meta.get("esfera", "").lower() != esfera.lower():
            continue
        atual = melhores.get(meta["arquivo"])
        if atual is None or trecho["similaridade"] > atual["similaridade"]:
            melhores[meta["arquivo"]] = trecho
    return melhores


def recuperar_documentos_com_perfil(
    mensagem_usuario: str,
    perfil_extraido: Optional[dict] = None,
    k: int = TOP_K,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
    categoria: Optional[str] = None,
    esfera: Optional[str] = None,
) -> dict:
    """Busca pelo relato original e pela consulta enriquecida, aplica filtros e deduplica por programa."""
    query_busca = montar_query_enriquecida(mensagem_usuario, perfil_extraido)
    consultas = list(dict.fromkeys([mensagem_usuario, query_busca]))

    melhores: dict[str, dict] = {}
    for consulta in consultas:
        parciais = _buscar_por_consulta(
            consulta,
            k_busca=k * 4,
            limiar_similaridade=limiar_similaridade,
            categoria=categoria,
            esfera=esfera,
        )
        for arquivo, trecho in parciais.items():
            atual = melhores.get(arquivo)
            if atual is None or trecho["similaridade"] > atual["similaridade"]:
                melhores[arquivo] = trecho

    programas = sorted(melhores.values(), key=lambda t: t["similaridade"], reverse=True)[:k]
    contexto = montar_contexto(programas) if programas else ""
    return {
        "query_busca": query_busca,
        "programas": programas,
        "documentos": _dividir_contexto(contexto),
        "contexto": contexto,
    }


def executar_buscas_rewoo(
    mensagem_usuario: str,
    perfil_extraido: Optional[dict],
    passos: list[dict],
    k_por_passo: int = 2,
    k_total: int = 8,
    limiar_similaridade: float = LIMIAR_SIMILARIDADE,
) -> dict:
    """Executa todas as subconsultas planejadas pelo ReWOO Planner sem chamar LLM (Worker)."""
    evidencias_rewoo: dict[str, list[str]] = {}
    melhores_globais: dict[str, dict] = {}
    queries_executadas: list[str] = []

    for idx, passo in enumerate(passos or [], 1):
        id_ev = str(passo.get("id_evidencia") or f"#E{idx}").strip()
        if not id_ev.startswith("#"):
            id_ev = f"#{id_ev}"
        query_passo = str(passo.get("query_busca") or passo.get("foco_necessidade") or mensagem_usuario).strip()
        categoria = (passo.get("categoria") or "").strip() or None
        esfera = (passo.get("esfera") or "").strip() or None

        queries_executadas.append(f"{id_ev}: {query_passo}")
        parciais = _buscar_por_consulta(
            query_passo,
            k_busca=max(k_por_passo * 4, 8),
            limiar_similaridade=limiar_similaridade,
            categoria=categoria,
            esfera=esfera,
        )
        if not parciais and (categoria or esfera):
            parciais = _buscar_por_consulta(
                query_passo,
                k_busca=max(k_por_passo * 4, 8),
                limiar_similaridade=limiar_similaridade,
            )

        progs_passo = sorted(parciais.values(), key=lambda t: t["similaridade"], reverse=True)[:k_por_passo]
        ctx_passo = montar_contexto(progs_passo) if progs_passo else ""
        evidencias_rewoo[id_ev] = _dividir_contexto(ctx_passo)

        for prog in progs_passo:
            arq = prog["meta"]["arquivo"]
            atual = melhores_globais.get(arq)
            if atual is None or prog["similaridade"] > atual["similaridade"]:
                melhores_globais[arq] = prog

    if len(melhores_globais) < k_total:
        complementar = recuperar_documentos_com_perfil(
            mensagem_usuario, perfil_extraido, k=k_total, limiar_similaridade=limiar_similaridade
        )
        for prog in complementar["programas"]:
            arq = prog["meta"]["arquivo"]
            if arq not in melhores_globais:
                melhores_globais[arq] = prog

    limite_final = max(k_total, len(passos or []))
    programas_consolidados = sorted(
        melhores_globais.values(), key=lambda t: t["similaridade"], reverse=True
    )[:limite_final]
    contexto = montar_contexto(programas_consolidados) if programas_consolidados else ""

    return {
        "query_busca": " | ".join(queries_executadas) if queries_executadas else mensagem_usuario,
        "evidencias_rewoo": evidencias_rewoo,
        "programas": programas_consolidados,
        "documentos": _dividir_contexto(contexto),
        "contexto": contexto,
    }
