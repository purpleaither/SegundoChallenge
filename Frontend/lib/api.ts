// Current GitHub backend: Back-end/main.py, proxied by Next on the same origin.
export type Programa = {
  programa: string; titulo: string; orgao: string; esfera: string;
  categoria: string; resumo: string; publico_alvo: string; criterios: string;
  lei: string | null; url: string | null; similaridade?: number;
};
export type Referencia = { id: string; title: string; url: string };
export type RespostaApi = {
  resposta: string; fora_do_escopo: boolean; programas: Programa[]; aviso: string;
  fontes?: Referencia[];
  apoio?: string | null; fala?: string; status?: string; padrao?: string | null;
};
type Benefit = {
  id: string; name: string; current_name: string; agency_id: string; scope: string;
  category: string; summary: string; benefit_type: string; audience: string;
  criteria: string[]; legislation_base: string; legislation_url: string; source_url: string;
};
type AssistantResponse = { sources?: Referencia[]; answer: string; benefits: Benefit[]; notice: string; support_message: string | null; speech_text: string; status: string; execution_pattern: string | null };

export function adaptAssistantResponse(result: AssistantResponse): RespostaApi {
  if (typeof result?.answer !== 'string' || !Array.isArray(result.benefits) || typeof result.notice !== 'string'
      || typeof result.speech_text !== 'string'
      || !['sucesso', 'sucesso_com_encaminhamento_ajuda', 'encaminhamento_ajuda', 'bloqueado_guardrail', 'erro_api'].includes(result.status)
      || (result.support_message !== null && typeof result.support_message !== 'string')) {
    throw new Error('O servidor retornou uma resposta inválida. Tente novamente.');
  }
  return {
    resposta: result.answer,
    aviso: result.notice,
    fontes: result.sources,
    apoio: result.support_message, fala: result.speech_text,
    status: result.status, padrao: result.execution_pattern,
    fora_do_escopo: result.status === 'bloqueado_guardrail',
    programas: result.benefits.map(p => ({
      programa: p.id,
      titulo: p.current_name && p.current_name !== p.name ? `${p.name} (nome atual: ${p.current_name})` : p.name,
      orgao: p.agency_id, esfera: p.scope, categoria: p.category,
      resumo: [p.summary, p.benefit_type && `Tipo de benefício: ${p.benefit_type}.`].filter(Boolean).join(' '),
      publico_alvo: p.audience, criterios: p.criteria.join(' '),
      lei: p.legislation_base || null, url: p.legislation_url || p.source_url || null,
    })),
  };
}

export async function perguntar(pergunta: string, signal?: AbortSignal, request: typeof fetch = fetch): Promise<RespostaApi> {
  const response = await request('/api/orientar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: pergunta }), signal, cache: 'no-store',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === 'string' ? body.detail : null;
    throw new Error(detail ?? 'Não consegui falar com o servidor agora. Tente de novo em instantes.');
  }
  return adaptAssistantResponse(await response.json());
}
