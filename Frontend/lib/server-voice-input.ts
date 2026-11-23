export const RECORDING_LIMIT_MS = 60_000;
export const AUDIO_LIMIT_BYTES = 8 * 1024 * 1024;

export function appendTranscript(draft: string, spoken: string) {
  const text = [draft.trim(), spoken.trim()].filter(Boolean).join(' ');
  return { text: text.slice(0, 1000), truncated: text.length > 1000 };
}

export async function transcribeAudio(audio: Blob, signal: AbortSignal, request: typeof fetch = fetch, preview = false): Promise<string> {
  if (!audio.size) throw new Error('Não há áudio na gravação. Tente novamente.');
  if (audio.size > AUDIO_LIMIT_BYTES) throw new Error('Gravação muito grande. Grave uma pergunta mais curta.');
  let response: Response;
  try {
    response = await request(preview ? '/api/stt?preview=true' : '/api/stt', { method: 'POST', body: audio, signal, cache: 'no-store', headers: { 'Content-Type': audio.type || 'audio/webm' } });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error('Não foi possível transcrever. Verifique a conexão e tente novamente.');
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      413: 'Gravação muito longa. Grave no máximo 60 segundos.',
      415: 'Formato de gravação não suportado. Tente outro navegador.',
      422: 'Não consegui processar o áudio. Grave novamente.',
      429: 'A transcrição está ocupada. Tente novamente em instantes.',
    };
    throw new Error(messages[response.status] || 'Não foi possível transcrever. Verifique a conexão e tente novamente.');
  }
  const result = await response.json();
  if (typeof result.text !== 'string') throw new Error('O serviço retornou uma transcrição inválida.');
  return result.text.trim();
}

/** Independent PCM WAV snapshots retain all spoken context, without container fragments. */
export function pcmWav(chunks: Float32Array[], sampleRate: number, frames: number): Blob {
  const buffer = new ArrayBuffer(44 + frames * 2), view = new DataView(buffer);
  const label = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  label(0, 'RIFF'); view.setUint32(4, 36 + frames * 2, true); label(8, 'WAVE'); label(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); label(36, 'data'); view.setUint32(40, frames * 2, true);
  let index = 0;
  for (const chunk of chunks) for (const value of chunk) {
    if (index >= frames) break;
    const sample = Math.max(-1, Math.min(1, value));
    view.setInt16(44 + index++ * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

export class ProgressiveTranscriber {
  private chunks: Float32Array[] = [];
  private frames = 0;
  private attempted = 0;
  private text = '';
  private busy: Promise<void> | null = null;
  private finishing = false;
  private cancelled = false;
  private abort = new AbortController();
  private sampleRate: number;
  private notify: (text: string) => void;
  private request: (audio: Blob, signal: AbortSignal, preview: boolean) => Promise<string>;
  constructor(sampleRate: number, notify: (text: string) => void,
    request: (audio: Blob, signal: AbortSignal, preview: boolean) => Promise<string> = (audio, signal, preview) => transcribeAudio(audio, signal, fetch, preview)) {
    this.sampleRate = sampleRate; this.notify = notify; this.request = request;
  }
  push(samples: Float32Array) {
    if (this.finishing || this.cancelled) return;
    const remaining = this.sampleRate * (RECORDING_LIMIT_MS / 1000) - this.frames;
    const chunk = samples.slice(0, remaining);
    if (!chunk.length) return;
    this.chunks.push(chunk); this.frames += chunk.length;
    this.partial();
  }
  private partial() {
    if (this.busy || this.finishing || this.cancelled || this.frames < this.sampleRate * 2.5 || this.frames - this.attempted < this.sampleRate * 2) return;
    const frames = this.frames; this.attempted = frames;
    this.busy = this.snapshot(frames).then(() => {}, () => {
      // A failed preview is retried with more context, or reported on finalization.
    }).finally(() => { this.busy = null; this.partial(); });
  }
  private async snapshot(frames: number, preview = true) {
    const timeout = new AbortController();
    const cancel = () => timeout.abort();
    this.abort.signal.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(cancel, 30_000);
    try {
      const text = await this.request(pcmWav(this.chunks, this.sampleRate, frames), timeout.signal, preview);
      if (this.cancelled) return;
      this.text = text;
      if (text) this.notify(text);
    } catch (error) {
      if (timeout.signal.aborted && !this.cancelled) throw new Error('A transcrição demorou demais. Revise o texto já reconhecido.');
      throw error;
    } finally { clearTimeout(timer); this.abort.signal.removeEventListener('abort', cancel); }
  }
  async finish(): Promise<string> {
    this.finishing = true;
    await this.busy;
    if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
    if (!this.frames) throw new Error('Não há áudio na gravação. Tente novamente.');
    await this.snapshot(this.frames, false);
    if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
    return this.text;
  }
  cancel() { this.cancelled = true; this.abort.abort(); this.chunks = []; }
}
