'use client'
import { useState } from 'react'

export function PdfPreview({ url, title }: { url: string; title: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div className="text-xs text-muted-foreground">
        Preview unavailable.{' '}
        <a href={url} target="_blank" rel="noopener" className="underline">
          Open PDF in new tab
        </a>
      </div>
    )
  }
  return (
    <iframe
      src={url}
      className="w-full h-96 border rounded"
      title={title}
      onError={() => setFailed(true)}
    />
  )
}
