'use client'
import { useCallback, useRef, useState } from 'react'
import { apiStream } from '@/lib/api-client'
import type { BackendError, DesignIntent, GenerateResponse, SSEEvent } from '@/lib/types'

export type GenerateState = 'idle' | 'generating' | 'done' | 'error'

export function useGenerateStream() {
  const [state, setState] = useState<GenerateState>('idle')
  const [error, setError] = useState<BackendError | null>(null)
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(
    async (intent: DesignIntent, materialName: string, sessionId: string | null) => {
      setState('generating')
      setError(null)
      setEvents([])
      setResult(null)
      const ctrl = new AbortController()
      abortRef.current = ctrl
      try {
        for await (const ev of apiStream(
          '/generate',
          { intent, material_name: materialName, session_id: sessionId },
          ctrl.signal,
        )) {
          setEvents((prev) => [...prev, ev])
          if (ev.event === 'error') {
            setError(ev.data)
            setState('error')
            return
          }
          if (ev.event === 'final' && 'cache_hit' in ev.data) {
            setResult(ev.data)
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

  const abort = useCallback(() => abortRef.current?.abort(), [])

  return { state, error, events, result, start, abort }
}
