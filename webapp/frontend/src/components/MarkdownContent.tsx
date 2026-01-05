import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { cn } from '@/lib/utils'

interface MarkdownContentProps {
  content: string
  className?: string
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div className={cn('markdown-content', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const isInline = !match && !className
            
            if (isInline) {
              return (
                <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                  {children}
                </code>
              )
            }

            return (
              <div className="my-4 rounded-lg overflow-hidden border">
                <SyntaxHighlighter
                  style={oneDark}
                  language={match ? match[1] : 'text'}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: 0,
                    fontSize: '0.875rem',
                  }}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              </div>
            )
          },
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto rounded-lg border border-border">
                <table className="w-full border-collapse text-sm">{children}</table>
              </div>
            )
          },
          thead({ children }) {
            return (
              <thead className="bg-muted/50">{children}</thead>
            )
          },
          th({ children }) {
            return (
              <th className="px-4 py-3 text-left font-semibold border-b border-border whitespace-nowrap">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="px-4 py-3 border-b border-border/50">{children}</td>
            )
          },
          tr({ children }) {
            return (
              <tr className="hover:bg-muted/30 transition-colors">{children}</tr>
            )
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {children}
              </a>
            )
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-primary pl-4 my-4 italic text-muted-foreground">
                {children}
              </blockquote>
            )
          },
          ul({ children }) {
            return <ul className="list-disc list-inside my-3 space-y-1">{children}</ul>
          },
          ol({ children }) {
            return <ol className="list-decimal list-inside my-3 space-y-1">{children}</ol>
          },
          h1({ children }) {
            return <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="text-xl font-semibold mt-5 mb-3">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="text-lg font-medium mt-4 mb-2">{children}</h3>
          },
          p({ children }) {
            return <p className="my-3 leading-relaxed">{children}</p>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
