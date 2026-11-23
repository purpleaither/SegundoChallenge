export type RecognitionResultEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
export type RecognitionEngine = {
  lang: string; continuous: boolean; interimResults: boolean;
  onstart: (() => void) | null; onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  start(): void; stop(): void; abort(): void;
};
export type RecognitionConstructor = new () => RecognitionEngine;
export function voiceInputError(error: string): string {
  switch (error) {
    case 'not-allowed': case 'service-not-allowed': return 'O acesso ao microfone foi negado. Permita o microfone no navegador ou digite sua dúvida.';
    case 'audio-capture': return 'Não encontrei um microfone disponível. Verifique a conexão ou digite sua dúvida.';
    case 'network': return 'O serviço de transcrição não respondeu. Verifique a conexão e tente novamente.';
    case 'no-speech': return 'Não consegui ouvir sua fala. Tente gravar novamente.';
    case 'language-not-supported': return 'A transcrição em português não está disponível neste navegador.';
    default: return 'Não foi possível transcrever o áudio. Tente novamente ou digite sua dúvida.';
  }
}
export function transcriptText(results: RecognitionResultEvent['results']) {
  return Array.from(results, result => result[0]?.transcript ?? '').join(' ').trim();
}
