'use client'
import { useCallback, useState } from 'react'
import { apiPost } from '@/lib/api-client'
import type { AnalysisResult, BackendError, DesignIntent } from '@/lib/types'

export type AnalyzeState = 'idle' | 'running' | 'done' | 'error'

export function useAnalyze() {
  const [state, setState] = useState<AnalyzeState>('idle')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(
    async (intent: DesignIntent, materialName: string) => {
      setState('running')
      setError(null)
      setResult(null)
      try {
        const data = await apiPost<AnalysisResult>('/analyze', {
          intent,
          material_name: materialName,
        })
        setResult(data)
        setState('done')
      } catch (e: unknown) {
        const body = (e as { body?: BackendError }).body
        setError(body ?? { code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, result, error, run }
}
