'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Bot, Check, ChevronDown, ExternalLink, LoaderCircle, Menu, MessageCircle, Mic, ShieldCheck, Sparkles, Square, UserRound, Volume2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { perguntar, sintetizarAudio, transcreverAudio, type Beneficio } from '@/lib/api'
import { dividirTextoParaFala, limparMarkdownParaFala } from '@/lib/audio'

type Message =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; speechText?: string; benefits?: Beneficio[]; supportMessage?: string | null; notice?: string; erro?: boolean }

const suggestions = ['Quais benefícios posso receber?', 'Como faço meu Cadastro Único?', 'Tem ajuda para mães solo?']
const AVISO = 'Isto é só uma orientação. Quem confirma se você tem direito é o órgão responsável. Procure o CRAS mais próximo para fazer o pedido.'

function criteriosLegiveis(criterios: string[]) {
  const legiveis = criterios.filter((criterio) => criterio && !criterio.startsWith('Não especificado'))
  return legiveis.length ? legiveis.join(' ') : 'A base não detalha os critérios; confirme no órgão responsável.'
}

function BenefitCard({ beneficio }: { beneficio: Beneficio }) {
  const fonte = beneficio.source_url || beneficio.legislation_url
  return (
    <article className="benefit-card">
      <div className="card-tag"><Check size={12} /> {beneficio.scope} · {beneficio.agency_id}</div>
      <h3>{beneficio.current_name || beneficio.name}</h3>
      <p>{beneficio.summary}</p>
      <dl className="card-details">
        {beneficio.audience && <><dt>Para quem é</dt><dd>{beneficio.audience}</dd></>}
        <dt>Quem pode pedir</dt><dd>{criteriosLegiveis(beneficio.criteria)}</dd>
        {beneficio.legislation_base && <><dt>Lei</dt><dd>{beneficio.legislation_base}</dd></>}
      </dl>
      {fonte && <a className="card-link" href={fonte} target="_blank" rel="noreferrer">Fonte oficial <ExternalLink size={13} /></a>}
    </article>
  )
}

function MessageRow({
  message,
  index,
  speaking,
  onToggleSpeech,
}: {
  message: Message
  index: number
  speaking: boolean
  onToggleSpeech: (index: number, text: string) => void
}) {
  const isAssistant = message.role === 'assistant'
  const benefits = isAssistant ? message.benefits ?? [] : []
  const notice = isAssistant ? message.notice || (benefits.length ? AVISO : '') : ''
  const speechText = isAssistant
    ? message.speechText || [message.text, message.supportMessage].filter(Boolean).join('\n\n')
    : ''
  return (
    <div className={`message-row ${message.role}`}>
      <div className={`message-avatar ${message.role}`}>{isAssistant ? <Bot size={17} /> : <UserRound size={16} />}</div>
      <div className="message-content">
        <div className="message-heading">
          <span className="message-author">{isAssistant ? 'GovernancIA' : 'Você'}</span>
          {isAssistant && speechText && !message.erro && (
            <button
              className="speech-button"
              type="button"
              aria-label={speaking ? 'Parar áudio da resposta' : 'Ouvir resposta'}
              onClick={() => onToggleSpeech(index, speechText)}
            >
              {speaking ? <Square size={13} /> : <Volume2 size={15} />}
              {speaking ? 'Parar áudio' : 'Ouvir resposta'}
            </button>
          )}
        </div>
        {message.text && (message.role === 'assistant' && !message.erro
          ? (
            <div className="answer-markdown">
              <ReactMarkdown
                components={{
                  a: ({ href, children }) => href && /^https?:\/\//i.test(href)
                    ? <a href={href} target="_blank" rel="noreferrer">{children}</a>
                    : <>{children}</>,
                }}
              >
                {message.text}
              </ReactMarkdown>
            </div>
          )
          : <p className={isAssistant && message.erro ? 'message-error' : undefined}>{message.text}</p>)}
        {isAssistant && message.supportMessage && <p className="message-notice">{message.supportMessage}</p>}
        {benefits.length > 0 && <div className="benefit-cards">{benefits.map((beneficio) => <BenefitCard key={beneficio.id} beneficio={beneficio} />)}</div>}
        {notice && <p className="message-notice"><ShieldCheck size={13} /> {notice}</p>}
      </div>
    </div>
  )
}

export default function Page() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [recording, setRecording] = useState(false)
  const [microphonePending, setMicrophonePending] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [audioError, setAudioError] = useState('')
  const [speakingMessageId, setSpeakingMessageId] = useState<number | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  const transcriptionRef = useRef<AbortController | null>(null)
  const speechRef = useRef<AbortController | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recorderTimerRef = useRef<number | null>(null)
  const recordingGenerationRef = useRef(0)
  const discardRecordingRef = useRef(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, loading])
  useEffect(() => () => {
    requestRef.current?.abort()
    transcriptionRef.current?.abort()
    speechRef.current?.abort()
    recordingGenerationRef.current += 1
    discardRecordingRef.current = true
    if (recorderTimerRef.current !== null) window.clearTimeout(recorderTimerRef.current)
    if (recorderRef.current) {
      recorderRef.current.ondataavailable = null
      recorderRef.current.onstop = null
      if (recorderRef.current.state !== 'inactive') recorderRef.current.stop()
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    audioRef.current?.pause()
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
  }, [])

  function pararLeitura() {
    speechRef.current?.abort()
    speechRef.current = null
    audioRef.current?.pause()
    audioRef.current = null
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
    audioUrlRef.current = null
    setSpeakingMessageId(null)
  }

  function pararGravacao(descartar = false) {
    if (recorderTimerRef.current !== null) {
      window.clearTimeout(recorderTimerRef.current)
      recorderTimerRef.current = null
    }
    if (descartar) discardRecordingRef.current = true
    const recorder = recorderRef.current
    if (recorder?.state === 'recording') {
      recorder.stop()
      return
    }
    if (descartar) {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      recorderRef.current = null
      setRecording(false)
    }
  }

  async function iniciarGravacao() {
    if (recording || microphonePending || transcribing || loading) return
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAudioError('Este navegador não oferece gravação de áudio. Use uma versão recente do Chrome ou Edge.')
      return
    }

    pararLeitura()
    setAudioError('')
    setMicrophonePending(true)
    discardRecordingRef.current = false
    const generation = ++recordingGenerationRef.current
    let stream: MediaStream | null = null

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (generation !== recordingGenerationRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }

      const activeStream = stream
      const mimeType = [
        'audio/webm;codecs=opus',
        'audio/ogg;codecs=opus',
        'audio/mp4',
      ].find((candidate) => MediaRecorder.isTypeSupported(candidate))
      const recorder = new MediaRecorder(activeStream, mimeType ? { mimeType } : undefined)
      const chunks: Blob[] = []
      streamRef.current = activeStream
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data)
      }
      recorder.onerror = () => {
        discardRecordingRef.current = true
        setAudioError('O navegador não conseguiu gravar o áudio. Tente novamente.')
        pararGravacao(true)
      }
      recorder.onstop = async () => {
        if (recorderTimerRef.current !== null) {
          window.clearTimeout(recorderTimerRef.current)
          recorderTimerRef.current = null
        }
        activeStream.getTracks().forEach((track) => track.stop())
        if (streamRef.current === activeStream) streamRef.current = null
        if (recorderRef.current === recorder) recorderRef.current = null
        setRecording(false)

        if (discardRecordingRef.current) {
          discardRecordingRef.current = false
          return
        }

        const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        if (audio.size === 0) {
          setAudioError('Não foi capturado áudio. Verifique o microfone e tente novamente.')
          return
        }

        const controller = new AbortController()
        transcriptionRef.current = controller
        setTranscribing(true)
        let timedOut = false
        const timeout = window.setTimeout(() => {
          timedOut = true
          controller.abort()
        }, 90_000)
        try {
          const transcript = await transcreverAudio(audio, controller.signal)
          if (!transcript) {
            setAudioError('Não reconheci fala nesse áudio. Tente gravar novamente.')
            return
          }
          setInput((current) => [current.trim(), transcript].filter(Boolean).join(' '))
          setAudioError('')
        } catch (error) {
          if (timedOut) {
            setAudioError('A transcrição passou do limite de 90 segundos. Tente um áudio mais curto.')
          } else if (!controller.signal.aborted) {
            setAudioError(error instanceof Error ? error.message : 'Falha ao transcrever. Tente novamente.')
          }
        } finally {
          window.clearTimeout(timeout)
          if (transcriptionRef.current === controller) {
            transcriptionRef.current = null
            setTranscribing(false)
          }
        }
      }

      recorder.start()
      setRecording(true)
      recorderTimerRef.current = window.setTimeout(() => {
        if (recorder.state === 'recording') {
          setAudioError('Limite de 60 segundos atingido; finalizando a gravação.')
          recorder.stop()
        }
      }, 60_000)
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())
      if (streamRef.current === stream) streamRef.current = null
      recorderRef.current = null
      discardRecordingRef.current = false
      const denied = error instanceof Error && error.name === 'NotAllowedError'
      setAudioError(denied
        ? 'Permita o acesso ao microfone nas configurações do navegador e tente novamente.'
        : 'Não foi possível iniciar o microfone. Verifique se há um dispositivo disponível.')
    } finally {
      if (generation === recordingGenerationRef.current) setMicrophonePending(false)
    }
  }

  async function alternarLeitura(index: number, text: string) {
    if (speakingMessageId === index) {
      pararLeitura()
      return
    }

    pararLeitura()
    const speechText = limparMarkdownParaFala(text)
    const chunks = dividirTextoParaFala(speechText)
    if (chunks.length === 0) {
      setAudioError('Não há texto para converter em áudio.')
      return
    }

    setAudioError('')
    setSpeakingMessageId(index)
    const controller = new AbortController()
    speechRef.current = controller
    try {
      for (const chunk of chunks) {
        const audioBlob = await sintetizarAudio(chunk, controller.signal)
        if (controller.signal.aborted) break
        const audioUrl = URL.createObjectURL(audioBlob)
        const player = new Audio(audioUrl)
        audioUrlRef.current = audioUrl
        audioRef.current = player
        try {
          await new Promise<void>((resolve, reject) => {
            const cleanup = () => controller.signal.removeEventListener('abort', onAbort)
            const onAbort = () => {
              cleanup()
              player.pause()
              resolve()
            }
            player.onended = () => {
              cleanup()
              resolve()
            }
            player.onerror = () => {
              cleanup()
              reject(new Error('O navegador não conseguiu reproduzir o áudio gerado.'))
            }
            controller.signal.addEventListener('abort', onAbort, { once: true })
            if (controller.signal.aborted) {
              onAbort()
              return
            }
            player.play().catch((error: unknown) => {
              cleanup()
              reject(error)
            })
          })
        } finally {
          URL.revokeObjectURL(audioUrl)
          if (audioUrlRef.current === audioUrl) audioUrlRef.current = null
          if (audioRef.current === player) audioRef.current = null
        }
        if (controller.signal.aborted) break
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setAudioError(error instanceof Error ? error.message : 'Não foi possível reproduzir a resposta.')
      }
    } finally {
      if (speechRef.current === controller) {
        speechRef.current = null
        setSpeakingMessageId(null)
      }
    }
  }

  async function sendMessage(value = input) {
    const text = value.trim()
    if (!text || loading || recording || microphonePending || transcribing) return
    pararLeitura()
    setMessages((current) => [...current, { role: 'user', text }])
    setInput('')
    setLoading(true)

    const controller = new AbortController()
    requestRef.current = controller
    try {
      const resposta = await perguntar(text, controller.signal)
      setMessages((current) => [...current, {
        role: 'assistant',
        text: resposta.answer,
        speechText: resposta.speech_text,
        benefits: resposta.benefits,
        supportMessage: resposta.support_message,
        notice: resposta.notice,
      }])
    } catch (error) {
      if (controller.signal.aborted) return
      const text = error instanceof Error ? error.message : 'Algo deu errado. Tente de novo.'
      setMessages((current) => [...current, { role: 'assistant', text, erro: true }])
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }

  function newChat() {
    requestRef.current?.abort()
    requestRef.current = null
    transcriptionRef.current?.abort()
    transcriptionRef.current = null
    recordingGenerationRef.current += 1
    pararGravacao(true)
    pararLeitura()
    setLoading(false)
    setTranscribing(false)
    setMicrophonePending(false)
    setAudioError('')
    setMessages([])
    setMenuOpen(false)
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <div className="brand"><div className="brand-mark"><MessageCircle size={20} strokeWidth={2.5} /></div><span>Governanc<span className="brand-ai">IA</span></span></div>
        <div className="sidebar-content">
          <button className="new-chat" onClick={newChat}><span>＋</span> Nova conversa</button>
          <p className="sidebar-label">SEU ESPAÇO</p>
          <button className="side-link active"><MessageCircle size={17} /> Conversa atual</button>
          <div className="sidebar-note"><div className="note-icon"><ShieldCheck size={17} /></div><p><strong>Informação segura</strong><br />Seus dados não são solicitados nesta conversa.</p></div>
        </div>
        <div className="sidebar-bottom">
          <div className="df-mini"><span className="df-star">✳</span><span>Distrito Federal</span><span className="df-dot" /></div>
          <div className="profile"><div className="profile-avatar"><UserRound size={17} /></div><div><strong>Visitante</strong><small>Atendimento digital</small></div><ChevronDown size={16} className="profile-chevron" /></div>
        </div>
      </aside>
      {menuOpen && <button className="mobile-backdrop" aria-label="Fechar menu" onClick={() => setMenuOpen(false)} />}

      <section className="chat-area">
        <header className="topbar">
          <button className="mobile-menu" aria-label="Abrir menu" onClick={() => setMenuOpen(!menuOpen)}><Menu size={20} /></button>
          <div className="topbar-title"><span className="status-dot" /> Assistente virtual do DF</div>
          <button className="about-button"><ShieldCheck size={15} /> Sobre o atendimento</button>
        </header>

        <div className="chat-scroll" aria-live="polite">
          {messages.length === 0 ? (
            <div className="welcome-wrap">
              <div className="welcome-icon"><div className="welcome-spark"><Sparkles size={18} /></div><Bot size={35} strokeWidth={1.6} /></div>
              <div className="eyebrow"><span /> BEM-VINDA(O) AO GOVERNANCIA</div>
              <h1>Oi! Vamos encontrar<br />o apoio certo <em>para você.</em></h1>
              <p className="welcome-copy">Sou a GovernancIA, sua assistente para descobrir benefícios sociais disponíveis no Distrito Federal. Me conta o que você precisa — sem complicação.</p>
              <div className="suggestion-label">VOCÊ PODE PERGUNTAR</div>
              <div className="suggestions">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => sendMessage(suggestion)}>{suggestion}<ArrowUp size={15} className="suggestion-arrow" /></button>)}</div>
              <div className="welcome-foot"><ShieldCheck size={15} /> Orientação clara, acolhedora e feita para quem vive no DF.</div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <MessageRow
                  key={index}
                  message={message}
                  index={index}
                  speaking={speakingMessageId === index}
                  onToggleSpeech={alternarLeitura}
                />
              ))}
              {loading && (
                <div className="message-row assistant">
                  <div className="message-avatar assistant"><Bot size={17} /></div>
                  <div className="message-content"><span className="message-author">GovernancIA</span><div className="typing" aria-label="Buscando resposta"><span /><span /><span /></div></div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        <div className="composer-wrap">
          {(recording || microphonePending || transcribing || audioError) && (
            <p className={`audio-feedback${audioError ? ' has-error' : ''}`} role={audioError ? 'alert' : 'status'}>
              {audioError || (recording
                ? 'Gravando… clique no botão para parar (limite de 60 segundos).'
                : transcribing
                  ? 'Transcrevendo o áudio localmente…'
                  : 'Aguardando permissão do microfone…')}
            </p>
          )}
          <form className="composer" onSubmit={(event) => { event.preventDefault(); sendMessage() }}>
            <label className="sr-only" htmlFor="message">Digite sua mensagem</label>
            <textarea id="message" rows={1} maxLength={1000} placeholder="Escreva sua dúvida por aqui..." value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); sendMessage() } }} />
            <button
              className={`voice-button${recording ? ' is-recording' : ''}`}
              type="button"
              aria-label={recording ? 'Parar gravação' : 'Gravar pergunta'}
              aria-pressed={recording}
              disabled={loading || microphonePending || transcribing}
              onClick={() => recording ? pararGravacao() : void iniciarGravacao()}
            >
              {microphonePending || transcribing
                ? <LoaderCircle size={17} className="spinning" />
                : recording
                  ? <Square size={15} />
                  : <Mic size={18} />}
            </button>
            <button className="send-button" type="submit" aria-label="Enviar mensagem" disabled={!input.trim() || loading || recording || microphonePending || transcribing}><ArrowUp size={19} /></button>
          </form>
          <div className="composer-caption">
            <span><ShieldCheck size={13} /> Não compartilhe dados pessoais ou bancários.</span>
            <span>Áudio: até 60 s, transcrito localmente e não salvo.</span>
            <span>GovernancIA pode cometer erros. <a href="https://www.df.gov.br/" target="_blank" rel="noreferrer">Confirme fontes oficiais.</a></span>
          </div>
        </div>
      </section>
    </main>
  )
}