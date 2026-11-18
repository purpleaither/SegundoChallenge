import { ChevronDown, ExternalLink, Landmark } from "lucide-react";
import type { Programa } from "@/lib/api";
import { ReadingTopics, ReadingTerms } from "./reading-topics";

export default function BenefitCard({ programa: p }: { programa: Programa }) {
  const criteria = !p.criterios || p.criterios.startsWith("Não especificado")
    ? "A base não informa os critérios. Confirme no órgão responsável ou no CRAS."
    : p.criterios;
  return (
    <article className="benefit-card">
      <span className="card-tag"><Landmark size={16} />{p.esfera}</span>
      <h3>{p.titulo}</h3>
      <section className="reading-section"><h4>O que é</h4><ReadingTopics text={p.resumo} /></section>
      {p.publico_alvo && <section className="reading-section"><h4>Para quem é</h4><ReadingTopics text={p.publico_alvo} /></section>}
      <section className="reading-section"><h4>Quem pode pedir</h4><ReadingTopics text={criteria} /></section>
      <ReadingTerms text={[p.resumo, p.publico_alvo, p.criterios].join(" ")} />
      <details className="source-details">
        <summary>Ver texto e referência da base <ChevronDown size={18} /></summary>
        <dl>
          <dt>Descrição original</dt><dd>{p.resumo}</dd>
          {p.publico_alvo && <><dt>Público informado</dt><dd>{p.publico_alvo}</dd></>}
          {p.criterios && <><dt>Critérios originais</dt><dd>{p.criterios}</dd></>}
          <dt>Órgão responsável</dt><dd>{p.orgao}</dd>
          {p.lei && <><dt>Legislação</dt><dd>{p.lei}</dd></>}
        </dl>
      </details>
      {p.url && <a href={p.url} target="_blank" rel="noreferrer">Consultar fonte oficial <ExternalLink size={16} /></a>}
    </article>
  );
}
