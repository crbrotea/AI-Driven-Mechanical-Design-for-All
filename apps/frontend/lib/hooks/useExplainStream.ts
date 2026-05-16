'use client'
import { useCallback, useState } from 'react'
import { apiStream } from '@/lib/api-client'
import type {
  AnalysisResult,
  BackendError,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export type ExplainState = 'idle' | 'streaming' | 'done' | 'error'

export function useExplainStream() {
  const [state, setState] = useState<ExplainState>('idle')
  const [streamedText, setStreamedText] = useState('')
  const [report, setReport] = useState<NaturalReport | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const start = useCallback(
    async (
      intent: DesignIntent,
      analysis: AnalysisResult,
      sessionId: string | null,
    ) => {
      setState('streaming')
      setStreamedText('')
      setReport(null)
      setError(null)
      try {
        for await (const ev of apiStream('/explain', {
          intent,
          analysis_result: analysis,
          session_id: sessionId,
        })) {
          if (ev.event === 'chunk' && typeof (ev.data as { text?: string }).text === 'string') {
            const text = (ev.data as { text: string }).text
            setStreamedText((prev) => prev + text)
          } else if (ev.event === 'final' && (ev.data as { report?: NaturalReport }).report) {
            setReport((ev.data as { report: NaturalReport }).report)
          } else if (ev.event === 'error') {
            setError(ev.data as BackendError)
            setState('error')
            return
          }
        }
        setState('done')
      } catch (e: unknown) {
        setError({ code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, streamedText, report, error, start }
}
