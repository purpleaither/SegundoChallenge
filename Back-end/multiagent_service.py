"""HTTP boundary for the repository's LangGraph pipeline. Never silently falls back to RAG."""
from __future__ import annotations

import os
import re
import sys
import threading
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
lock = threading.Lock()


class PipelineUnavailable(Exception):
    pass


class PipelineBusy(Exception):
    pass


def configured() -> bool:
    load_dotenv(ROOT / '.env', override=False)
    load_dotenv(ROOT / 'sistema_multiagente/.env', override=False)
    return bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))


def execute_pipeline(question: str) -> dict:
    if not configured():
        raise PipelineUnavailable('Assistente indisponível. A configuração do serviço precisa ser concluída.')
    if not lock.acquire(blocking=False):
        raise PipelineBusy()
    try:
        from sistema_multiagente.graph import executar_fluxo
        return executar_fluxo(question)
    except PipelineUnavailable:
        raise
    except Exception as error:
        # Do not expose provider exceptions, prompts, keys or personal profiles in HTTP errors.
        raise PipelineUnavailable('Não foi possível concluir a orientação agora. Tente novamente em instantes.') from error
    finally:
        lock.release()


def normalize(text: str) -> str:
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c)).split())


def response_from_state(state: dict, benefits: list) -> dict:
    status = state.get('status_api', '')
    if status not in {'sucesso', 'sucesso_com_encaminhamento_ajuda', 'encaminhamento_ajuda', 'bloqueado_guardrail', 'erro_api'}:
        raise PipelineUnavailable('Não foi possível concluir a orientação agora. Tente novamente em instantes.')
    support = (state.get('mensagem_apoio') or '').strip() or None
    final = (state.get('resposta_final') or '').strip()
    answer = (state.get('resposta_beneficios') or '').strip()
    if not answer:
        answer = final.replace(support, '').strip(' \n=-') if support else final
    if not answer and not support:
        raise PipelineUnavailable('O assistente não conseguiu concluir a orientação. Tente novamente.')
    # Only expose programs actually retrieved and allowed by the structured analysis.
    retrieved = {normalize(name) for doc in state.get('documentos_encontrados') or []
                 for name in re.findall(r'^Programa oficial:\s*(.+)$', doc, flags=re.MULTILINE)}
    allowed = {'elegivel', 'potencialmente_elegivel', 'criterio_nao_especificado_na_base'}
    analysis = (state.get('analise_elegibilidade') or {}).get('programas_avaliados') or []
    by_name = {normalize(b.name): b for b in benefits}
    by_name.update({normalize(b.current_name): b for b in benefits if b.current_name})
    matches, seen = [], set()
    sources = [
        {'id': b.id, 'title': b.name, 'url': b.legislation_url or b.source_url}
        for b in benefits if normalize(b.name) in retrieved and (b.legislation_url or b.source_url)
    ]
    if status in {'sucesso', 'sucesso_com_encaminhamento_ajuda'}:
        for item in analysis:
            name = normalize(item.get('nome_programa', ''))
            benefit = by_name.get(name)
            if item.get('status_elegibilidade') not in allowed or not benefit or benefit.id in seen:
                continue
            if normalize(benefit.name) not in retrieved and name not in retrieved:
                continue
            seen.add(benefit.id); matches.append(benefit)
    # The graph's final message includes any support message: use it once for speech.
    spoken = final or '\n\n'.join(part for part in [answer, support] if part)
    return {
        'answer': answer, 'support_message': support, 'speech_text': spoken,
        'benefits': matches, 'sources': sources, 'notice': '', 'status': status,
        'execution_pattern': state.get('padrao_execucao'),
    }
