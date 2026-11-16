'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Bot, Check, ChevronDown, ExternalLink, Menu, MessageCircle, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import { perguntar, type Programa } from '@/lib/api'

type Message =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; programas?: Programa[]; erro?: boolean }

const suggestions = ['Quais benefícios posso receber?', 'Como faço meu Cadastro Único?', 'Tem ajuda para mães solo?']

const AVISO = 'Isto é só uma orientação. Quem confirma se você tem direito é o órgão responsável. Procure o CRAS mais próximo para fazer o pedido.'

function textoDaResposta(programas: Programa[], resposta: string) {
  if (programas.length === 0) return resposta
  const n = programas.length
  return `Encontrei ${n} ${n === 1 ? 'programa que pode' : 'programas que podem'} ter relação com a sua situação:`
}

function criteriosLegiveis(criterios: string) {
  return !criterios || criterios.startsWith('Não especificado') ? 'A base não detalha os critérios; confirme no CRAS.' : criterios
}

function BenefitCard({ programa }: { programa: Programa }) {
  return (
    <article className="benefit-card">
      <div className="card-tag"><Check size={12} /> {programa.esfera} · {programa.orgao}</div>
      <h3>{programa.titulo}</h3>
      <p>{programa.resumo}</p>
      <dl className="card-details">
        {programa.publico_alvo && <><dt>Para quem é</dt><dd>{programa.publico_alvo}</dd></>}
        <dt>Quem pode pedir</dt><dd>{criteriosLegiveis(programa.criterios)}</dd>
        {programa.lei && <><dt>Lei</dt><dd>{programa.lei}</dd></>}
      </dl>
      {programa.url && <a className="card-link" href={programa.url} target="_blank" rel="noreferrer">Fonte oficial <ExternalLink size={13} /></a>}
    </article>
  )
}

function MessageRow({ message }: { message: Message }) {
  const isAssistant = message.role === 'assistant'
  const programas = isAssistant ? message.programas ?? [] : []
  return (
    <div className={`message-row ${message.role}`}>
      <div className={`message-avatar ${message.role}`}>{isAssistant ? <Bot size={17} /> : <UserRound size={16} />}</div>
      <div className="message-content">
        <span className="message-author">{isAssistant ? 'GovernancIA' : 'Você'}</span>
        <p className={isAssistant && message.erro ? 'message-error' : undefined}>{message.text}</p>
        {programas.length > 0 && <>
          <div className="benefit-cards">{programas.map((programa) => <BenefitCard key={programa.programa} programa={programa} />)}</div>
          <p className="message-notice"><ShieldCheck size={13} /> {AVISO}</p>
        </>}
      </div>
    </div>
  )
}

export default function Page() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const requestRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, loading])
  useEffect(() => () => requestRef.current?.abort(), [])

  async function sendMessage(value = input) {
    const text = value.trim()
    if (!text || loading) return
    setMessages((current) => [...current, { role: 'user', text }])
    setInput('')
    setLoading(true)

    const controller = new AbortController()
    requestRef.current = controller
    try {
      const { resposta, programas } = await perguntar(text, controller.signal)
      setMessages((current) => [...current, { role: 'assistant', text: textoDaResposta(programas, resposta), programas }])
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
    setLoading(false)
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
              {messages.map((message, index) => <MessageRow key={index} message={message} />)}
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
          <form className="composer" onSubmit={(event) => { event.preventDefault(); sendMessage() }}>
            <label className="sr-only" htmlFor="message">Digite sua mensagem</label>
            <textarea id="message" rows={1} maxLength={1000} placeholder="Escreva sua dúvida por aqui..." value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); sendMessage() } }} />
            <button className="send-button" type="submit" aria-label="Enviar mensagem" disabled={!input.trim() || loading}><ArrowUp size={19} /></button>
          </form>
          <div className="composer-caption"><span><ShieldCheck size={13} /> Não compartilhe dados pessoais ou bancários.</span><span>GovernancIA pode cometer erros. <a href="https://www.df.gov.br/" target="_blank" rel="noreferrer">Confirme informações oficiais.</a></span></div>
        </div>
      </section>
    </main>
  )
}
