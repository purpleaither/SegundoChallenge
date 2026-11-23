/** Presentation only: preserve the source wording, amounts, conditions and order. */
export function readingTopics(text: string): string[] {
  const lines = text.trim().split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const topics: string[] = [];
  for (const line of lines) {
    const content = line.replace(/^(?:[-*•]\s+|\d+[.)]\s+)/, "");
    // Split only at sentence boundaries, never decimals, legal numbers or semicolons.
    const sentences = content.split(/(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý])/u);
    for (const sentence of sentences) {
      const previous = topics[topics.length - 1];
      if (previous && /\b(?:art|arts|dr|dra|sr|sra|av|inc)\.$/i.test(previous)) {
        topics[topics.length - 1] += ` ${sentence}`;
      } else topics.push(sentence);
    }
  }
  return topics;
}

const vocabulary = [
  { pattern: /\bper capita\b/i, term: "Per capita", meaning: "Por pessoa." },
  { pattern: /pecuniári[oa]s?/i, term: "Pecuniário", meaning: "Em dinheiro." },
  { pattern: /\bdeferimento\b/i, term: "Deferimento", meaning: "Aprovação de um pedido." },
  { pattern: /\bindeferimento\b/i, term: "Indeferimento", meaning: "Recusa de um pedido." },
  { pattern: /domicílio/i, term: "Domicílio", meaning: "Local onde a pessoa mora." },
];
export function readingTerms(text: string) {
  return vocabulary.filter(entry => entry.pattern.test(text)).map(({ term, meaning }) => ({ term, meaning }));
}
