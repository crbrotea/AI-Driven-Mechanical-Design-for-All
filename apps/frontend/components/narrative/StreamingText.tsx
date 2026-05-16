'use client'

export function StreamingText({ text }: { text: string }) {
  return (
    <pre className="text-xs whitespace-pre-wrap text-muted-foreground">
      {text}
      <span className="inline-block w-2 h-3 bg-current animate-pulse ml-0.5 align-middle" />
    </pre>
  )
}
