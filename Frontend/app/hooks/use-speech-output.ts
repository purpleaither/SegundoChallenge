"use client";
import { useEffect, useRef, useState } from 'react';
import { SpeechOutput, type PlaybackState } from '@/lib/speech-output';

export function useSpeechOutput() {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [state, setState] = useState<PlaybackState>({ id: null, status: 'idle', error: '' });
  const controller = useRef<SpeechOutput | null>(null);
  useEffect(() => {
    const available = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    setSupported(available);
    if (available) controller.current = new SpeechOutput(window.speechSynthesis, text => new SpeechSynthesisUtterance(text), setState);
    return () => { controller.current?.dispose(); controller.current = null; };
  }, []);
  return { supported, state, play: (id: string, text: string) => controller.current?.play(id, text), pause: () => controller.current?.pause(), resume: () => controller.current?.resume(), stop: () => controller.current?.stop() };
}
