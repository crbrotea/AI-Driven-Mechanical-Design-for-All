'use client'
import { useCallback, useRef, useState } from 'react'
import { apiStream } from '@/lib/api-client'
import type { BackendError, DesignIntent, SSEEvent } from '@/lib/types'

export type StreamState = 'idle' | 'streaming' | 'done' | 'error'

export function useInterpretStream() {
  const [state, setState] = useState<StreamState>('idle')
  const [error, setError] = useState<BackendError | null>(null)
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [intent, setIntent] = useState<DesignIntent | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(
    async (prompt: string, sessionId: string | null) => {
      setState('streaming')
      setError(null)
      setEvents([])
      setIntent(null)
      const ctrl = new AbortController()
      abortRef.current = ctrl
      try {
        for await (const ev of apiStream(
          '/interpret',
          { prompt, session_id: sessionId },
          ctrl.signal,
        )) {
          setEvents((prev) => [...prev, ev])
          if (ev.event === 'error') {
            setError(ev.data)
            setState('error')
            return
          }
          if (ev.event === 'final' && 'intent' in ev.data) {
            setIntent(ev.data.intent)
          }
        }
        setState('done')
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          setState('idle')
          return
        }
        setError({ code: 'connection_lost', message: 'Connection interrupted' })
        setState('error')
      }
    },
    [],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { state, error, events, intent, start, abort }
}
