export type PlaybackState = { id: string | null; status: 'idle' | 'loading' | 'speaking' | 'paused'; error: string };
const idle = (): PlaybackState => ({ id: null, status: 'idle', error: '' });
type SpeechEngine = Pick<SpeechSynthesis, 'speak' | 'cancel' | 'pause' | 'resume' | 'getVoices'>;

/** Small utterances avoid long-text truncation in browser speech engines. */
export function speechChunks(text: string, limit = 240): string[] {
  const chunks: string[] = [];
  let current = '';
  for (const word of text.trim().split(/\s+/).filter(Boolean)) {
    if (current && current.length + word.length + 1 > limit) { chunks.push(current); current = ''; }
    current += (current ? ' ' : '') + word;
  }
  if (current) chunks.push(current);
  return chunks;
}

export class SpeechOutput {
  private generation = 0;
  private state: PlaybackState = idle();
  private utterance: SpeechSynthesisUtterance | null = null;
  private engine: SpeechEngine;
  private createUtterance: (text: string) => SpeechSynthesisUtterance;
  private notify: (state: PlaybackState) => void;
  constructor(engine: SpeechEngine, createUtterance: (text: string) => SpeechSynthesisUtterance, notify: (state: PlaybackState) => void) {
    this.engine = engine; this.createUtterance = createUtterance; this.notify = notify;
  }
  private update(next: PlaybackState) { this.state = next; this.notify(next); }
  play(id: string, text: string) {
    this.stop();
    const chunks = speechChunks(text);
    if (!chunks.length) return;
    const generation = this.generation;
    this.update({ id, status: 'loading', error: '' });
    const voices = this.engine.getVoices();
    const voice = voices.find(v => /^pt[-_]BR$/i.test(v.lang)) ?? voices.find(v => /^pt\b/i.test(v.lang));
    const next = (index: number) => {
      if (generation !== this.generation) return;
      if (index === chunks.length) { this.utterance = null; this.update(idle()); return; }
      const utterance = this.createUtterance(chunks[index]);
      this.utterance = utterance;
      utterance.lang = 'pt-BR'; utterance.rate = 1;
      if (voice) utterance.voice = voice;
      utterance.onstart = () => { if (generation === this.generation) this.update({ id, status: 'speaking', error: '' }); };
      utterance.onend = () => { if (generation === this.generation) next(index + 1); };
      utterance.onerror = () => {
        if (generation !== this.generation) return;
        this.generation++; this.utterance = null;
        this.update({ id, status: 'idle', error: 'Não foi possível reproduzir a voz. Tente ouvir novamente.' });
      };
      try { this.engine.speak(utterance); } catch {
        if (generation === this.generation) this.update({ id, status: 'idle', error: 'A leitura em voz alta não está disponível agora.' });
      }
    };
    next(0);
  }
  pause() { if (this.state.status === 'speaking') { this.engine.pause(); this.update({ ...this.state, status: 'paused' }); } }
  resume() { if (this.state.status === 'paused') { this.engine.resume(); this.update({ ...this.state, status: 'speaking' }); } }
  stop() { this.generation++; if (this.state.id) this.engine.cancel(); this.utterance = null; this.update(idle()); }
  dispose() { this.generation++; this.notify = () => {}; if (this.state.id) this.engine.cancel(); this.utterance = null; }
}
