/** Convert the supported Markdown presentation into speech without changing its claims. */
export function speechText(markdown: string): string {
  return markdown
    .replace(/<(script|style|iframe)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/```[^\n]*\n([\s\S]*?)```/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\((?:https?:\/\/|mailto:|tel:)[^)]*\)/g, '$1')
    .replace(/https?:\/\/[^\s<>]+/g, '')
    .replace(/<[^>]*>/g, '')
    .replace(/^\s{0,3}(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)/gm, '')
    .replace(/(?:\*\*|__|~~|`)/g, '')
    .replace(/\*([^*\n]+)\*/g, '$1')
    .replace(/^\s*[-=_]{3,}\s*$/gm, '')
    .replace(/\[\d+\]/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
