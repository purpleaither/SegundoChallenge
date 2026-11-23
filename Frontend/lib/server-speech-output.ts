import { speechChunks, type PlaybackState } from './speech-output';

type Dependencies = {
  fetchAudio: (text: string, signal: AbortSignal) => Promise<Blob>;
  createAudio: () => HTMLAudioElement;
  createUrl: (blob: Blob) => string;
  revokeUrl: (url: string) => void;
};
const idle = (): PlaybackState => ({ id: null, status: 'idle', error: '' });

export function ttsSegments(text: string): string[] {
  // Respect the API's hard limit even for long tokens such as URLs.
  return speechChunks(text, 300).flatMap(chunk => {
    const parts: string[] = [];
    for (let start = 0; start < chunk.length; start += 600) parts.push(chunk.slice(start, start + 600));
    return parts;
  });
}

export async function fetchTtsAudio(text: string, signal: AbortSignal, request: typeof fetch = fetch): Promise<Blob> {
  for (let attempt = 0; attempt < 4; attempt++) {
    if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
    const timeout = new AbortController();
    const abort = () => timeout.abort();
    signal.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(abort, 20000);
    try {
      const response = await request('/api/tts', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }), signal: timeout.signal, cache: 'no-store',
      });
      if (response.status === 429 && attempt < 3) {
        await new Promise<void>((resolve, reject) => {
          const finish = () => { signal.removeEventListener('abort', cancel); resolve(); };
          const wait = setTimeout(finish, 1000);
          const cancel = () => { clearTimeout(wait); reject(new DOMException('Cancelled', 'AbortError')); };
          signal.addEventListener('abort', cancel, { once: true });
          if (signal.aborted) cancel();
        });
        continue;
      }
      if (!response.ok) throw new Error('Não foi possível gerar o áudio. Tente novamente em instantes.');
      if (!response.headers.get('content-type')?.toLowerCase().includes('audio/wav')) throw new Error('O serviço não retornou um áudio válido.');
      const blob = await response.blob();
      if (blob.size <= 44 || blob.size > 8 * 1024 * 1024) throw new Error('O áudio retornado não pode ser reproduzido.');
      return blob;
    } catch (error) {
      if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
      if (timeout.signal.aborted) throw new Error('A geração do áudio demorou demais. Tente novamente.');
      throw error;
    } finally { clearTimeout(timer); signal.removeEventListener('abort', abort); }
  }
  throw new Error('A voz está ocupada. Tente novamente.');
}

/** Fetch one sentence group ahead; keep at most one response's audio in RAM. */
export class ServerSpeechOutput {
  private generation = 0;
  private state: PlaybackState = idle();
  private audio: HTMLAudioElement | null = null;
  private url: string | null = null;
  private abort: AbortController | null = null;
  private cachedText = '';
  private cache = new Map<number, Blob>();
  private cacheBytes = 0;
  private pending = new Map<number, Promise<Blob>>();
  private dependencies: Dependencies;
  private notify: (state: PlaybackState) => void;
  constructor(dependencies: Dependencies, notify: (state: PlaybackState) => void) { this.dependencies = dependencies; this.notify = notify; }
  private update(state: PlaybackState) { this.state = state; this.notify(state); }
  private releaseAudio() {
    if (this.audio) {
      this.audio.onplaying = null; this.audio.onended = null; this.audio.onerror = null;
      this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load(); this.audio = null;
    }
    if (this.url) { this.dependencies.revokeUrl(this.url); this.url = null; }
  }
  play(id: string, text: string) {
    this.stop();
    const segments = ttsSegments(text);
    if (!segments.length) return;
    if (text !== this.cachedText) { this.cache.clear(); this.cacheBytes = 0; this.cachedText = text; }
    const generation = this.generation;
    const abort = new AbortController(); this.abort = abort;
    this.update({ id, status: 'loading', error: '' });
    const fetchSegment = (index: number): Promise<Blob> => {
      const cached = this.cache.get(index);
      if (cached) return Promise.resolve(cached);
      const existing = this.pending.get(index);
      if (existing) return existing;
      const promise = this.dependencies.fetchAudio(segments[index], abort.signal).then(blob => {
        if (generation === this.generation && this.cacheBytes + blob.size <= 16 * 1024 * 1024) { this.cache.set(index, blob); this.cacheBytes += blob.size; }
        return blob;
      });
      // Prefetch errors are consumed later by the playback loop, without unhandled rejections.
      promise.catch(() => {});
      this.pending.set(index, promise);
      return promise;
    };
    const fail = (error: unknown) => {
      if (generation !== this.generation || abort.signal.aborted) return;
      this.generation++; abort.abort(); this.releaseAudio(); this.pending.clear();
      this.update({ id, status: 'idle', error: error instanceof Error ? error.message : 'Não foi possível reproduzir o áudio.' });
    };
    const next = async (index: number): Promise<void> => {
      if (generation !== this.generation) return;
      if (index >= segments.length) { this.releaseAudio(); this.pending.clear(); this.abort = null; this.update(idle()); return; }
      this.update({ id, status: 'loading', error: '' });
      try {
        const blob = await fetchSegment(index);
        if (generation !== this.generation || abort.signal.aborted) return;
        this.pending.delete(index);
        this.releaseAudio();
        const audio = this.dependencies.createAudio(); this.audio = audio;
        this.url = this.dependencies.createUrl(blob); audio.src = this.url;
        audio.onplaying = () => { if (generation === this.generation) this.update({ id, status: 'speaking', error: '' }); };
        audio.onended = () => { if (generation === this.generation) void next(index + 1); };
        audio.onerror = () => fail(new Error('Não foi possível reproduzir este áudio. Tente novamente.'));
        await audio.play();
        if (generation === this.generation && index + 1 < segments.length) void fetchSegment(index + 1);
      } catch (error) { fail(error); }
    };
    void next(0);
  }
  pause() { if (this.state.status === 'speaking' && this.audio) { this.audio.pause(); this.update({ ...this.state, status: 'paused' }); } }
  resume() {
    if (this.state.status !== 'paused' || !this.audio) return;
    const generation = this.generation;
    const id = this.state.id;
    this.update({ ...this.state, status: 'loading' });
    this.audio.play().catch(() => { if (generation === this.generation) { this.stop(); this.update({ id, status: 'idle', error: 'Não foi possível continuar a leitura. Tente ouvir novamente.' }); } });
  }
  stop() { this.generation++; this.abort?.abort(); this.abort = null; this.pending.clear(); this.releaseAudio(); this.update(idle()); }
  reset() { this.stop(); this.cache.clear(); this.cacheBytes = 0; this.cachedText = ''; }
  dispose() { this.notify = () => {}; this.reset(); }
}
