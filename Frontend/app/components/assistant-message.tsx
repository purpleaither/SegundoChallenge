import { ChevronDown } from 'lucide-react';
import type { Programa, Referencia } from '@/lib/api';
import MarkdownAnswer from './markdown-answer';
import BenefitCard from './benefit-card';

export default function AssistantMessage({ text, programas = [], notice, support, sources, failed = false }: { text: string; programas?: Programa[]; notice?: string; support?: string | null; sources?: Referencia[]; failed?: boolean }) {
  const references = sources ?? programas.filter(p => p.url).map(p => ({ id: p.programa, title: p.titulo, url: p.url! }));
  return <>
    {text && <div className={`bubble ${failed ? 'error' : ''}`}><MarkdownAnswer text={text} /></div>}
    {support && <section className="support-message" aria-label="Orientação adicional de apoio">
      <h2>Apoio e proteção</h2><MarkdownAnswer text={support} />
    </section>}
    {!!references.length && <ol className="response-sources" aria-label="Fontes oficiais consultadas">
      {references.map((source, index) => <li key={source.id} value={index + 1}>
        <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
      </li>)}
    </ol>}
    {!!programas.length && <details className="response-details">
      <summary>Ver detalhes dos programas <ChevronDown size={18} /></summary>
      <div className="benefit-cards">{programas.map(p => <BenefitCard key={p.programa} programa={p} />)}</div>
    </details>}
    {notice && <p className="result-notice">{notice}</p>}
  </>;
}
