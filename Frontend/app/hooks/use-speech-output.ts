"use client";
import { useEffect, useRef, useState } from 'react';
import type { PlaybackState } from '@/lib/speech-output';
import { ServerSpeechOutput, fetchTtsAudio } from '@/lib/server-speech-output';

export function useSpeechOutput() {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [state, setState] = useState<PlaybackState>({ id: null, status: 'idle', error: '' });
  const controller = useRef<ServerSpeechOutput | null>(null);
  useEffect(() => {
    const available = 'Audio' in window && 'fetch' in window;
    setSupported(available);
    if (available) controller.current = new ServerSpeechOutput({
      fetchAudio: fetchTtsAudio, createAudio: () => new Audio(),
      createUrl: blob => URL.createObjectURL(blob), revokeUrl: url => URL.revokeObjectURL(url),
    }, setState);
    return () => { controller.current?.dispose(); controller.current = null; };
  }, []);
  return {
    supported, state,
    play: (id: string, text: string) => controller.current?.play(id, text),
    pause: () => controller.current?.pause(), resume: () => controller.current?.resume(),
    stop: () => controller.current?.stop(), reset: () => controller.current?.reset(),
  };
}
