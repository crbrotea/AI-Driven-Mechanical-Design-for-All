'use client'
import { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { useInterpretStream } from '@/lib/hooks/useInterpretStream'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { StreamingIndicator } from './StreamingIndicator'

type HistoryItem = { role: 'user' | 'assistant'; content: string }

export function ChatPanel({
  sessionId,
  initialPrompt = '',
  onIntentReady,
}: {
  sessionId: string | null
  initialPrompt?: string
  onIntentReady: (intent: unknown) => void
}) {
  const t = useTranslations('chat')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const { state, events, intent, start } = useInterpretStream()
  const intentNotifiedRef = useRef(false)

  async function submit(prompt: string) {
    intentNotifiedRef.current = false
    setHistory((h) => [...h, { role: 'user', content: prompt }])
    await start(prompt, sessionId)
  }

  // When intent arrives, notify parent + add assistant summary
  useEffect(() => {
    if (state === 'done' && intent && !intentNotifiedRef.current) {
      intentNotifiedRef.current = true
      setHistory((h) => [
        ...h,
        { role: 'assistant', content: `${intent.type} — ${Object.keys(intent.fields).length} fields` },
      ])
      onIntentReady(intent)
    }
  }, [state, intent, onIntentReady])

  return (
    <aside className="flex h-full flex-col border-r border-border" aria-label="Chat">
      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        {history.length === 0 && state === 'idle' && (
          <div className="text-center text-sm text-muted-foreground">{t('placeholder')}</div>
        )}
        {history.map((m, i) => (
          <ChatMessage key={i} role={m.role} content={m.content} />
        ))}
        {state === 'streaming' && <StreamingIndicator events={events} />}
      </div>
      <ChatInput onSubmit={submit} disabled={state === 'streaming'} initialValue={initialPrompt} />
    </aside>
  )
}
