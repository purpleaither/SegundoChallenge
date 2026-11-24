const TTS_CHUNK_LIMIT = 500

export function limparMarkdownParaFala(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/[*_~`>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function dividirTextoParaFala(text: string): string[] {
  const palavras = text.trim().split(/\s+/).filter(Boolean)
  const partes: string[] = []
  let atual = ''
  const tamanho = (value: string) => Array.from(value).length

  for (const palavra of palavras) {
    const caracteres = Array.from(palavra)
    while (caracteres.length > TTS_CHUNK_LIMIT) {
      if (atual) {
        partes.push(atual)
        atual = ''
      }
      partes.push(caracteres.splice(0, TTS_CHUNK_LIMIT).join(''))
    }

    const restante = caracteres.join('')
    if (!restante) continue
    const proximo = atual ? `${atual} ${restante}` : restante
    if (tamanho(proximo) > TTS_CHUNK_LIMIT) {
      partes.push(atual)
      atual = restante
    } else {
      atual = proximo
    }
  }

  if (atual) partes.push(atual)
  return partes
}
