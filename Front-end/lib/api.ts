// Cliente da API do assistente (rag/api.py). As chamadas vão para /api/*, que o Next
// repassa ao backend Python (ver next.config.mjs).

export type Programa = {
  programa: string
  titulo: string
  orgao: string
  esfera: string
  categoria: string
  resumo: string
  publico_alvo: string
  criterios: string
  lei: string | null
  url: string | null
  similaridade: number
}

export type RespostaApi = {
  resposta: string
  fora_do_escopo: boolean
  programas: Programa[]
}

export async function perguntar(pergunta: string, signal?: AbortSignal): Promise<RespostaApi> {
  const resposta = await fetch('/api/perguntar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pergunta }),
    signal,
  })
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null)
    const detalhe = typeof corpo?.detail === 'string' ? corpo.detail : null
    throw new Error(detalhe ?? 'Não consegui falar com o servidor agora. Tente de novo em instantes.')
  }
  return resposta.json()
}