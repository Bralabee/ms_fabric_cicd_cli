import { useState, useCallback } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Check, Copy, FileCode } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { CodeBlock as CodeBlockType } from '@/lib/api'

interface CodeBlockProps {
  codeBlock: CodeBlockType
  className?: string
}

export function CodeBlock({ codeBlock, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  
  // Support both 'content' (backend) and 'code' (legacy) field names
  const codeContent = codeBlock.content || codeBlock.code || ''

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(codeContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [codeContent])

  const languageMap: Record<string, string> = {
    bash: 'bash',
    shell: 'bash',
    sh: 'bash',
    python: 'python',
    py: 'python',
    yaml: 'yaml',
    yml: 'yaml',
    json: 'json',
    typescript: 'typescript',
    ts: 'typescript',
    javascript: 'javascript',
    js: 'javascript',
    powershell: 'powershell',
    ps1: 'powershell',
    dockerfile: 'dockerfile',
    docker: 'dockerfile',
  }

  const language = languageMap[codeBlock.language?.toLowerCase() || 'bash'] || codeBlock.language || 'bash'

  return (
    <div className={cn('code-block rounded-lg overflow-hidden border', className)}>
      {/* Header */}
      <div className="flex items-center justify-between bg-muted px-4 py-2 border-b">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileCode className="h-4 w-4" />
          {codeBlock.filename && (
            <span className="font-mono">{codeBlock.filename}</span>
          )}
          {!codeBlock.filename && (
            <span className="capitalize">{language}</span>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="h-8 px-2"
        >
          {copied ? (
            <>
              <Check className="h-4 w-4 mr-1 text-green-500" />
              <span className="text-xs">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-4 w-4 mr-1" />
              <span className="text-xs">Copy</span>
            </>
          )}
        </Button>
      </div>

      {/* Code content */}
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: '0.875rem',
        }}
        showLineNumbers={codeContent.split('\n').length > 5}
      >
        {codeContent}
      </SyntaxHighlighter>

      {/* Description */}
      {codeBlock.description && (
        <div className="bg-muted/50 px-4 py-2 text-sm text-muted-foreground border-t">
          {codeBlock.description}
        </div>
      )}
    </div>
  )
}
