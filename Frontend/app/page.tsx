"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronRight,
  GraduationCap,
  Heart,
  Home,
  House,
  Info,
  Landmark,
  MessageCircle,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet,
  Zap,
} from "lucide-react";
import { perguntar, type Programa } from "@/lib/api";
import { ReadingTopics } from "./components/reading-topics";
import BenefitCard from "./components/benefit-card";
import { useVoiceInput } from "./hooks/use-voice-input";
import { useSpeechOutput } from "./hooks/use-speech-output";
import { RecordButton, VoiceInputStatus, ReplyAudio } from "./components/voice-controls";

type View = "home" | "chat" | "about";
type Message = {
  role: "user" | "assistant";
  text: string;
  programas?: Programa[];
  erro?: boolean;
};
const suggestions = [
  "Quais benefícios posso receber?",
  "Como faço meu Cadastro Único?",
  "Tem ajuda para mães solo?",
];
const categories = [
  {
    title: "Renda e família",
    subtitle: "Apoio no dia a dia",
    icon: Users,
    color: "blue",
    question: "Quais benefícios de renda e apoio à família estão disponíveis?",
  },
  {
    title: "Moradia",
    subtitle: "Um lugar para viver",
    icon: House,
    color: "orange",
    question: "Quais programas de apoio à moradia estão disponíveis?",
  },
  {
    title: "Educação",
    subtitle: "Novas oportunidades",
    icon: GraduationCap,
    color: "purple",
    question: "Quais benefícios e programas de educação estão disponíveis?",
  },
  {
    title: "Saúde",
    subtitle: "Cuidado para você",
    icon: Heart,
    color: "pink",
    question: "Quais programas ajudam no acesso a medicamentos e saúde?",
  },
  {
    title: "Água e energia",
    subtitle: "Economia nas contas",
    icon: Zap,
    color: "teal",
    question: "Como conseguir desconto nas contas de água e energia?",
  },
  {
    title: "Cadastro Único",
    subtitle: "Entenda como funciona",
    icon: Wallet,
    color: "green",
    question: "Como faço meu Cadastro Único?",
  },
];
const navigation = [
  { id: "home" as View, label: "Início", icon: Home },
  { id: "chat" as View, label: "Conversa", icon: MessageCircle },
  { id: "about" as View, label: "Sobre", icon: Info },
];
function Brand() {
  return (
    <span className="brand">
      <svg
        className="computer-brand"
        width="44"
        height="28"
        viewBox="0 0 600 378"
        aria-hidden="true"
      >
        <path
          fill="#1351B4"
          fillRule="evenodd"
          d="M85 0h430a30 30 0 0 1 30 30v280H55V30A30 30 0 0 1 85 0Zm9 40v230h412V40Z"
        />
        <path
          fill="#071D41"
          d="M15 326a9 9 0 0 1 9-9h552a9 9 0 0 1 9 9v8a44 44 0 0 1-44 44H59a44 44 0 0 1-44-44Z"
        />
        <rect x="254" y="333" width="92" height="17" rx="8.5" fill="#FFFFFF" />
        <path
          transform="translate(0 15)"
          fill="#071D41"
          d="M300 226 208 139c-49-46 19-113 64-69l28 28 28-28c45-44 113 23 64 69Z"
        />
      </svg>
      <span>
        Gu<span className="brand-ia">IA</span> Social
      </span>
    </span>
  );
}
export default function Page() {
  const [view, setView] = useState<View>("home");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const voice = useVoiceInput(setInput);
  const speech = useSpeechOutput();
  const audio = { ...speech, play: (id: string, text: string) => { voice.cancel(); speech.play(id, text); } };
  const requestRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (view === "chat")
      endRef.current?.scrollIntoView({
        behavior:
          document.documentElement.dataset.reduceMotion === "true" ||
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "instant"
            : "smooth",
        block: "end",
      });
  }, [messages, loading, view]);
  useEffect(() => () => requestRef.current?.abort(), []);
  function navigate(next: View) {
    if (next !== view) { voice.cancel(); speech.stop(); }
    setView(next);
  }
  function newChat() {
    voice.cancel(); speech.stop();
    requestRef.current?.abort();
    requestRef.current = null;
    setLoading(false);
    setMessages([]);
    setInput("");
    navigate("chat");
  }
  async function sendMessage(value = input) {
    const text = value.trim();
    if (!text || loading || voice.active) return;
    speech.stop();
    navigate("chat");
    setMessages((current) => [...current, { role: "user", text }]);
    setInput("");
    setLoading(true);
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const { resposta, programas } = await perguntar(text, controller.signal);
      setMessages((current) => [
        ...current,
        { role: "assistant", text: resposta, programas },
      ]);
    } catch (error) {
      if (!controller.signal.aborted)
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            text:
              error instanceof Error
                ? error.message
                : "Não foi possível buscar a resposta. Tente novamente.",
            erro: true,
          },
        ]);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }
  return (
    <main className="app-shell">
      <a className="skip-link" href="#main-content">
        Ir para o conteúdo
      </a>
      <aside className="sidebar" aria-label="Menu principal">
        <div className="sidebar-brand">
          <Brand />
        </div>
        <button className="new-chat" onClick={newChat}>
          <Plus size={19} />
          Nova conversa
        </button>
        <nav>
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${id === "chat" ? "chat-nav" : ""} ${view === id ? "active" : ""}`}
              onClick={() => navigate(id)}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon size={20} />
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <section className={`main-area view-${view}`}>
        <div id="main-content" className="view-content" tabIndex={-1}>
          {view === "home" && (
            <div className="home-scroll">
              <section className="hero">
                <div className="hero-copy">
                  <h1>
                    Como podemos
                    <br />
                    ajudar você hoje?
                  </h1>
                  <p>
                    Tire suas dúvidas sobre benefícios sociais com auxílio da{" "}
                    <strong>inteligência artificial</strong>.
                  </p>
                  <form
                    className="home-search"
                    onSubmit={(e) => {
                      e.preventDefault();
                      sendMessage();
                    }}
                  >
                    <Search size={22} />
                    <label className="sr-only" htmlFor="home-question">
                      Escreva sua dúvida aqui
                    </label>
                    <input
                      id="home-question"
                      maxLength={1000}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Escreva sua dúvida aqui"
                      readOnly={voice.active}
                    />
                    <RecordButton onBeforeStart={speech.stop} voice={voice} draft={input} disabled={loading} descriptionId="home-voice-status" />
                    <button
                      aria-label="Iniciar conversa"
                      disabled={!input.trim() || loading || voice.active}
                    >
                      <ArrowRight size={22} />
                    </button>
                  </form>
                  <VoiceInputStatus voice={voice} id="home-voice-status" />
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="art-chat art-back">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="art-chat art-front">
                    <MessageCircle size={48} strokeWidth={1.5} />
                    <div>
                      <span />
                      <span />
                    </div>
                    <span className="art-check">
                      <Check size={22} />
                    </span>
                  </div>
                </div>
              </section>
              <div className="home-content">
                <section>
                  <div className="section-heading">
                    <h2>Escolha um assunto que você deseja saber mais</h2>
                  </div>
                  <div className="category-grid">
                    {categories.map(
                      ({ title, icon: Icon, color, question }) => (
                        <button
                          className="category-card"
                          key={title}
                          onClick={() => sendMessage(question)}
                          disabled={loading || voice.active}
                        >
                          <span className={`category-icon ${color}`}>
                            <Icon size={26} strokeWidth={1.8} />
                          </span>
                          <strong>{title}</strong>
                          <ChevronRight className="category-arrow" size={18} />
                        </button>
                      ),
                    )}
                  </div>
                </section>
                <section className="common-questions">
                  <div className="section-heading">
                    <h2>Perguntas frequentes</h2>
                  </div>
                  <div>
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        disabled={loading || voice.active}
                        onClick={() => sendMessage(s)}
                      >
                        <MessageCircle size={18} />
                        <span>{s}</span>
                        <ArrowRight size={18} />
                      </button>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          )}
          {view === "chat" && (
            <>
              <div className="chat-heading">
                <span className="assistant-icon">
                  <MessageCircle size={28} />
                </span>
                <div>
                  <h1>
                    Gu<span className="brand-ia">IA</span> Social
                  </h1>
                </div>
              </div>
              <div className="chat-scroll">
                <div
                  className="messages"
                  role="log"
                  aria-label="Mensagens da conversa"
                  aria-live="polite"
                >
                  {messages.length === 0 && (
                    <div className="chat-welcome">
                      <h2>Como posso ajudar?</h2>
                      <ReplyAudio speech={audio} id="welcome" text={`Como posso ajudar? Você pode perguntar: ${suggestions.join(". ")}`} label="orientações da conversa" buttonText="Ouvir orientações" />
                      <div className="chat-suggestions">
                        {suggestions.map((s) => (
                          <button key={s} onClick={() => sendMessage(s)}>
                            {s}
                            <ArrowRight size={17} />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {messages.map((m, i) => (
                    <div key={i} className={`message-row ${m.role}`}>
                      <span className="message-label">
                        {m.role === "assistant" ? "GuIA Social" : "Você"}
                      </span>
                      {m.role === "assistant" && <ReplyAudio speech={audio} id={`reply-${i}`} text={m.text} label={`resposta ${i + 1}`} />}
                      <div className={`bubble ${m.erro ? "error" : ""}`}>
                        {m.role === "assistant" && !m.erro
                          ? m.programas?.length
                            ? `Encontrei ${m.programas.length === 1 ? "um programa que pode" : `${m.programas.length} programas que podem`} ter relação com a sua situação:`
                            : <ReadingTopics text={m.text} />
                          : m.text}
                      </div>
                      {!!m.programas?.length && (
                        <>
                          <div className="benefit-cards">
                            {m.programas.map((p) => (
                              <BenefitCard key={p.programa} programa={p} />
                            ))}
                          </div>
                          <details className="response-details">
                            <summary>Ver resposta completa da base <ChevronDown size={18} /></summary>
                            <div className="source-response">{m.text}</div>
                          </details>
                          <p className="result-notice">
                            <Info size={16} />
                            Confirme os requisitos no órgão responsável ou no
                            CRAS.
                          </p>
                        </>
                      )}
                    </div>
                  ))}
                  {loading && (
                    <div className="message-row assistant">
                      <span className="message-label">GuIA Social</span>
                      <div className="bubble typing" role="status">
                        <span />
                        <span />
                        <span />
                        <small>Buscando orientações</small>
                      </div>
                    </div>
                  )}
                  <div ref={endRef} />
                </div>
              </div>
              <div className="composer-wrap">
                <form
                  className="composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    sendMessage();
                  }}
                >
                  <label className="sr-only" htmlFor="message">
                    Digite sua mensagem
                  </label>
                  <textarea
                    id="message"
                    rows={1}
                    maxLength={1000}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Escreva sua dúvida aqui"
                    readOnly={voice.active}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        sendMessage();
                      }
                    }}
                  />
                  <RecordButton onBeforeStart={speech.stop} voice={voice} draft={input} disabled={loading} descriptionId="chat-voice-status" />
                  <button
                    type="submit"
                    disabled={!input.trim() || loading || voice.active}
                    aria-label="Enviar mensagem"
                  >
                    <ArrowUp size={23} />
                  </button>
                </form>
                <VoiceInputStatus voice={voice} id="chat-voice-status" />
                <p>
                  <ShieldCheck size={14} />
                  Não compartilhe dados pessoais ou bancários.
                </p>
              </div>
            </>
          )}
          {view === "about" && (
            <div className="about-scroll">
              <section className="about-page">
                <div className="about-title">
                  <h1>
                    Sobre o Gu<span className="brand-ia">IA</span> Social
                  </h1>
                </div>
                <p>
                  Um assistente com <strong>inteligência artificial</strong>{" "}
                  para ajudar você a entender benefícios sociais e encontrar caminhos de apoio.
                </p>
                <div className="about-cards">
                  <article>
                    <div className="about-card-heading">
                      <Users size={25} />
                      <h2>Benefícios e apoio</h2>
                    </div>
                    <p>Conheça os programas e seus critérios de acesso.</p>
                  </article>
                  <article>
                    <div className="about-card-heading">
                      <Sparkles size={25} />
                      <h2>Orientação com IA</h2>
                    </div>
                    <p>Tire dúvidas com orientações simples.</p>
                  </article>
                  <article>
                    <div className="about-card-heading">
                      <Landmark size={25} />
                      <h2>Fontes oficiais</h2>
                    </div>
                    <p>Confira os detalhes nas fontes oficiais.</p>
                  </article>
                </div>
                <div className="about-notice">
                  <Info size={22} />
                  <p>
                    O <strong>GuIA Social</strong> orienta, mas não realiza
                    inscrições nem aprova benefícios. A IA pode{" "}
                    <strong>cometer erros</strong>; confirme as informações no{" "}
                    <strong>órgão responsável</strong> ou no{" "}
                    <strong>CRAS</strong>.
                  </p>
                </div>
                <button
                  className="primary-button"
                  onClick={() => navigate("chat")}
                >
                  Conversar
                  <ArrowRight size={19} />
                </button>
              </section>
            </div>
          )}
        </div>
        <nav className="bottom-nav" aria-label="Navegação principal">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              className={`${id === "chat" ? "chat-nav" : ""} ${view === id ? "active" : ""}`}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon size={23} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </section>
    </main>
  );
}
