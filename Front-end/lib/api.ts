export type Beneficio = {
  id: string
  agency_id: string
  name: string
  current_name: string
  summary: string
  audience: string
  criteria: string[]
  source_title: string
  source_url: string
  legislation_base: string
  legislation_url: string
  scope: string
}

export type OrientacaoResponse = {
  answer: string
  benefits: Beneficio[]
  notice: string
  sources: { id: string; title: string; url: string }[]
  support_message: string | null
  speech_text: string
  status:
    | 'sucesso'
    | 'sucesso_com_encaminhamento_ajuda'
    | 'sucesso_degradado'
    | 'sucesso_degradado_com_encaminhamento_ajuda'
    | 'encaminhamento_ajuda'
    | 'bloqueado_guardrail'
    | 'erro_api'
  execution_pattern: 'padrao' | 'rewoo' | 'reflexion' | null
}

function detalheDeErro(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  return typeof body.detail === 'string' ? body.detail : null
}

async function lancarErroApi(response: Response, fallback: string): Promise<never> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = null
  }
  throw new Error(detalheDeErro(body) ?? fallback)
}

export async function perguntar(pergunta: string, signal?: AbortSignal): Promise<OrientacaoResponse> {
  const resposta = await fetch('/api/orientar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: pergunta }),
    signal,
  })

  if (!resposta.ok) {
    await lancarErroApi(resposta, 'Não consegui falar com o servidor agora. Tente de novo em instantes.')
  }

  return resposta.json()
}

export async function transcreverAudio(audio: Blob, signal?: AbortSignal): Promise<string> {
  const contentType = audio.type.split(';', 1)[0] || 'audio/webm'
  const resposta = await fetch('/api/stt', {
    method: 'POST',
    headers: { 'Content-Type': contentType },
    body: audio,
    signal,
  })

  if (!resposta.ok) {
    await lancarErroApi(resposta, 'Não foi possível transcrever o áudio. Tente novamente.')
  }

  const body: unknown = await resposta.json()
  if (typeof body !== 'object' || body === null || !('text' in body) || typeof body.text !== 'string') {
    throw new Error('O serviço de transcrição retornou uma resposta inválida.')
  }
  return body.text.trim()
}

export async function sintetizarAudio(text: string, signal?: AbortSignal): Promise<Blob> {
  const resposta = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  })

  if (!resposta.ok) {
    await lancarErroApi(resposta, 'Não foi possível gerar o áudio da resposta. Tente novamente.')
  }
  return resposta.blob()
}
