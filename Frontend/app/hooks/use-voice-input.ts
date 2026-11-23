"use client";
import { useEffect, useRef, useState } from 'react';
import { RECORDING_LIMIT_MS, appendTranscript, ProgressiveTranscriber } from '@/lib/server-voice-input';

type VoiceState = 'idle' | 'requesting' | 'recording' | 'stopping';
type Session = {
  stream?: MediaStream; context?: AudioContext; source?: MediaStreamAudioSourceNode;
  capture?: AudioWorkletNode; mute?: GainNode; transcriber?: ProgressiveTranscriber;
  timer?: ReturnType<typeof setTimeout>; flushTimer?: ReturnType<typeof setTimeout>;
  finishing: boolean; finalized: boolean;
  finalize?: () => void;
};
function stopMicrophone(session: Session) {
  session.stream?.getTracks().forEach(track => { track.onended = null; track.stop(); });
}
function release(session: Session) {
  clearTimeout(session.timer); clearTimeout(session.flushTimer);
  session.transcriber?.cancel(); stopMicrophone(session);
  session.source?.disconnect(); session.mute?.disconnect();
  if (session.capture) { session.capture.port.onmessage = null; session.capture.port.close(); session.capture.disconnect(); }
  if (session.context && session.context.state !== 'closed') void session.context.close().catch(() => {});
}
export function useVoiceInput(onTranscript: (text: string) => void) {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [status, setStatus] = useState<VoiceState>('idle');
  const [notice, setNotice] = useState('');
  const current = useRef<Session | null>(null);
  const callback = useRef(onTranscript); callback.current = onTranscript;
  useEffect(() => {
    setSupported(window.isSecureContext && !!navigator.mediaDevices?.getUserMedia && typeof AudioContext !== 'undefined' && typeof AudioWorkletNode !== 'undefined');
    return () => { const session = current.current; current.current = null; if (session) release(session); };
  }, []);
  function cancel() {
    const session = current.current; current.current = null;
    if (session) release(session);
    setStatus('idle'); setNotice('');
  }
  function stop() {
    const session = current.current;
    if (!session || session.finishing) return;
    if (!session.capture) { cancel(); return; }
    session.finishing = true; setStatus('stopping'); clearTimeout(session.timer);
    // Flush the audio thread before closing it, so the last syllable is retained.
    session.capture.port.postMessage('flush'); stopMicrophone(session);
    session.flushTimer = setTimeout(() => session.finalize?.(), 1000);
  }
  async function start(draft: string) {
    if (current.current || supported !== true) return;
    if (draft.length >= 1000) { setNotice('O campo já atingiu 1.000 caracteres. Reduza o texto antes de gravar.'); return; }
    const session: Session = { finishing: false, finalized: false };
    current.current = session; setStatus('requesting'); setNotice('');
    const fail = (message: string) => {
      if (current.current !== session) return;
      current.current = null; release(session); setStatus('idle'); setNotice(message);
    };
    try {
      // Resume in the click handler, before permission awaits, for browser autoplay rules.
      const context = new AudioContext({ sampleRate: 16000 }); session.context = context;
      await context.resume();
      if (current.current !== session) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }, video: false });
      if (current.current !== session) { stream.getTracks().forEach(track => track.stop()); return; }
      session.stream = stream;
      await context.audioWorklet.addModule('/voice-capture.worklet.js');
      if (current.current !== session) return;
      const capture = new AudioWorkletNode(context, 'guia-voice-capture', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
      session.capture = capture;
      let frames = 0;
      session.transcriber = new ProgressiveTranscriber(context.sampleRate, spoken => {
        if (current.current !== session) return;
        const result = appendTranscript(draft, spoken);
        callback.current(result.text);
        if (result.truncated && !session.finishing) stop();
      });
      session.finalize = () => {
        if (current.current !== session || session.finalized) return;
        session.finalized = true; clearTimeout(session.flushTimer);
        session.source?.disconnect(); capture.disconnect();
        capture.port.onmessage = null;
        if (context.state !== 'closed') void context.close().catch(() => {});
        session.timer = setTimeout(() => fail('A transcrição demorou demais. O texto já reconhecido foi mantido para revisão.'), 90_000);
        void session.transcriber!.finish().then(spoken => {
          if (current.current !== session) return;
          if (!spoken) { fail('Não consegui ouvir sua fala. Tente gravar novamente.'); return; }
          const result = appendTranscript(draft, spoken);
          callback.current(result.text);
          current.current = null; release(session); setStatus('idle');
          setNotice(result.truncated ? 'Limite de 1.000 caracteres atingido. Revise o texto antes de enviar.' : 'Transcrição pronta. Revise o texto e clique em enviar.');
        }).catch(error => fail(error instanceof Error ? error.message : 'Não foi possível finalizar a transcrição. Revise o texto.'));
      };
      capture.port.onmessage = event => {
        if (current.current !== session || session.finalized) return;
        if (event.data.type === 'flushed') { session.finalize?.(); return; }
        if (event.data.type !== 'samples' || !(event.data.samples instanceof Float32Array)) return;
        frames += event.data.samples.length;
        session.transcriber!.push(event.data.samples);
        if (frames >= context.sampleRate * (RECORDING_LIMIT_MS / 1000) && !session.finishing) stop();
      };
      capture.onprocessorerror = () => fail('Falha na gravação. O texto já reconhecido foi mantido.');
      const source = context.createMediaStreamSource(stream); session.source = source;
      const mute = context.createGain(); mute.gain.value = 0; session.mute = mute;
      source.connect(capture); capture.connect(mute); mute.connect(context.destination);
      stream.getAudioTracks().forEach(track => { track.onended = () => { if (current.current === session) stop(); }; });
      setStatus('recording');
      session.timer = setTimeout(() => { if (current.current === session) stop(); }, RECORDING_LIMIT_MS);
    } catch (error) {
      const denied = error instanceof DOMException && ['NotAllowedError', 'SecurityError'].includes(error.name);
      fail(denied ? 'Permita o acesso ao microfone no navegador ou digite sua dúvida.' : 'Não foi possível iniciar o microfone. Verifique se ele está conectado e disponível.');
    }
  }
  return { supported, status, notice, active: status !== 'idle', start, stop, cancel };
}
