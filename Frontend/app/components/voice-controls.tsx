"use client";
import { Mic, Square, Volume2, Pause, Play } from 'lucide-react';
import type { useVoiceInput } from '../hooks/use-voice-input';
import type { useSpeechOutput } from '../hooks/use-speech-output';

type InputVoice = ReturnType<typeof useVoiceInput>;
export function RecordButton({ voice, draft, disabled, descriptionId, onBeforeStart }: { voice: InputVoice; draft: string; disabled: boolean; descriptionId: string; onBeforeStart?: () => void }) {
  const label = voice.active ? 'Parar gravação' : 'Gravar pergunta por áudio';
  return <button type="button" className={`voice-record ${voice.active ? 'is-recording' : ''}`} aria-label={label} title={label} aria-pressed={voice.active} aria-keyshortcuts="Space" aria-describedby={descriptionId} disabled={(!voice.active && disabled) || voice.supported !== true || voice.status === 'stopping'} onClick={() => { if (voice.active) voice.stop(); else { onBeforeStart?.(); voice.start(draft); } }}>{voice.active ? <Square className="voice-stop-symbol" size={20} aria-hidden="true" /> : <Mic size={23} aria-hidden="true" />}</button>;
}
export function VoiceInputStatus({ voice, id }: { voice: InputVoice; id: string }) {
  return <div className="voice-input-status" id={id}>
    <p role="status" aria-live="polite">{voice.active ? voice.status === 'requesting' ? 'Aguardando o microfone…' : voice.status === 'stopping' ? 'Finalizando a transcrição…' : 'Gravando. Fale sua dúvida e use o botão parar ao terminar.' : voice.notice || (voice.supported === false ? 'Gravação indisponível neste navegador. Você pode digitar sua dúvida.' : '')}</p>
  </div>;
}
export function ReplyAudio({ speech, id, text, label, buttonText = "Ouvir resposta" }: { speech: ReturnType<typeof useSpeechOutput>; id: string; text: string; label: string; buttonText?: string }) {
  const selected = speech.state.id === id;
  const playing = selected && speech.state.status !== 'idle';
  return <div className="reply-audio" role="group" aria-label={label}>
    {!playing && <button type="button" className="voice-action voice-listen" disabled={speech.supported !== true} onClick={() => speech.play(id, text)} aria-label={`Ouvir ${label}`}><Volume2 size={19} aria-hidden="true" />{buttonText}</button>}
    {playing && <>
      {speech.state.status === 'speaking' && <button type="button" className="voice-action" onClick={speech.pause} aria-label={`Pausar ${label}`}><Pause size={19} aria-hidden="true" />Pausar</button>}
      {speech.state.status === 'paused' && <button type="button" className="voice-action" onClick={speech.resume} aria-label={`Continuar ${label}`}><Play size={19} aria-hidden="true" />Continuar</button>}
      <button type="button" className="voice-action" onClick={speech.stop} aria-label={`Parar leitura da ${label}`}><Square className="voice-stop-symbol" size={18} aria-hidden="true" />Parar</button>
    </>}
    <span className="speech-status" role="status">{speech.supported === false ? 'Leitura em voz alta indisponível neste navegador.' : selected ? speech.state.error || (speech.state.status === 'loading' ? 'Preparando a leitura…' : speech.state.status === 'speaking' ? 'Lendo a resposta.' : speech.state.status === 'paused' ? 'Leitura pausada.' : '') : ''}</span>
  </div>;
}
