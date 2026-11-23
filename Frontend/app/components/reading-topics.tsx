import { readingTerms, readingTopics } from "@/lib/readable-text";

export function ReadingTopics({ text }: { text: string }) {
  const items = readingTopics(text);
  return <ul className="reading-topics">{items.map((item, index) => <li key={index}>{item}</li>)}</ul>;
}

export function ReadingTerms({ text }: { text: string }) {
  const terms = readingTerms(text);
  if (!terms.length) return null;
  return <details className="reading-terms"><summary>Entenda os termos</summary><dl>{terms.map(({ term, meaning }) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl></details>;
}
