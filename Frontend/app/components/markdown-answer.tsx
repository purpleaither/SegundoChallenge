import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function safeUrl(url: string) {
  return /^(https?:\/\/|mailto:|tel:)/i.test(url) ? url : '';
}
export default function MarkdownAnswer({ text }: { text: string }) {
  return <div className="markdown-answer"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={safeUrl}
    components={{
      h1: ({ children }) => <h2>{children}</h2>,
      h2: ({ children }) => <h2>{children}</h2>,
      a: ({ href, children }) => href ? <a href={href} target="_blank" rel="noreferrer">{children}</a> : <span>{children}</span>,
    }}>{text}</ReactMarkdown></div>;
}
