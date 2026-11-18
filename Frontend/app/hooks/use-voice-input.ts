"use client";
import { useEffect, useRef, useState } from 'react';
import { transcriptText, voiceInputError, type RecognitionEngine, type RecognitionConstructor } from '@/lib/voice-input';

type VoiceState = 'idle' | 'requesting' | 'recording' | 'stopping';
export function useVoiceInput(onTranscript: (text: string) => void) {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [status, setStatus] = useState<VoiceState>('idle');
  const [notice, setNotice] = useState('');
  const engineRef = useRef<RecognitionEngine | null>(null);
  const callback = useRef(onTranscript);
  callback.current = onTranscript;
  const constructorRef = useRef<RecognitionConstructor | null>(null);
  const stopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function clearStopTimer() { if (stopTimer.current) clearTimeout(stopTimer.current); stopTimer.current = null; }
  useEffect(() => {
    const browser = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    constructorRef.current = window.isSecureContext ? browser.SpeechRecognition ?? browser.webkitSpeechRecognition ?? null : null;
    setSupported(!!constructorRef.current);
    return () => { clearStopTimer(); const engine = engineRef.current; engineRef.current = null; try { engine?.abort(); } catch {} };
  }, []);
  function cancel() {
    clearStopTimer();
    const engine = engineRef.current; engineRef.current = null;
    try { engine?.abort(); } catch {}
    setStatus('idle'); setNotice('');
  }
  function stop() {
    if (!engineRef.current) return;
    if (status === 'requesting') { cancel(); return; }
    setStatus('stopping');
    const engine = engineRef.current;
    try {
      engine.stop();
      stopTimer.current = setTimeout(() => {
        if (engineRef.current !== engine) return;
        engineRef.current = null;
        try { engine.abort(); } catch {}
        setStatus('idle'); setNotice('Gravação encerrada. Revise o texto antes de enviar.');
      }, 4000);
    } catch { cancel(); }
  }
  function start(draft: string) {
    const Constructor = constructorRef.current;
    if (!Constructor || engineRef.current) return;
    if (draft.length >= 1000) { setNotice('O campo já atingiu 1.000 caracteres. Reduza o texto antes de gravar.'); return; }
    let engine: RecognitionEngine;
    try { engine = new Constructor(); } catch { setNotice('A gravação não está disponível neste navegador. Digite sua dúvida.'); return; }
    engineRef.current = engine;
    let heard = false; let failed = false;
    engine.lang = 'pt-BR'; engine.continuous = false; engine.interimResults = true;
    setNotice(''); setStatus('requesting');
    engine.onstart = () => { if (engineRef.current === engine) setStatus('recording'); };
    engine.onresult = event => {
      if (engineRef.current !== engine) return;
      const spoken = transcriptText(event.results);
      if (!spoken) return;
      heard = true;
      const text = [draft.trim(), spoken].filter(Boolean).join(' ');
      callback.current(text.slice(0, 1000));
      if (text.length >= 1000) { setNotice('Limite de 1.000 caracteres atingido. Revise o texto antes de enviar.'); engine.stop(); }
    };
    engine.onerror = event => {
      if (engineRef.current !== engine) return;
      failed = true; clearStopTimer();
      setNotice(voiceInputError(event.error));
      engineRef.current = null; setStatus('idle');
    };
    engine.onend = () => {
      if (engineRef.current !== engine) return;
      clearStopTimer(); engineRef.current = null; setStatus('idle');
      if (!failed && !heard) setNotice('Não consegui ouvir sua fala. Tente gravar novamente.');
      else if (!failed) setNotice('Transcrição pronta. Revise o texto e clique em enviar.');
    };
    try { engine.start(); } catch { engineRef.current = null; setStatus('idle'); setNotice('Não foi possível iniciar o microfone. Tente novamente.'); }
  }
  return { supported, status, notice, active: status !== 'idle', start, stop, cancel };
}
