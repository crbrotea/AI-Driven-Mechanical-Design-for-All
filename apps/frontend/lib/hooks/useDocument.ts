'use client'
import { useCallback, useState } from 'react'
import { apiPost } from '@/lib/api-client'
import type {
  AnalysisResult,
  BackendError,
  CachedArtifacts,
  Deliverables,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export type DocumentState = 'idle' | 'running' | 'done' | 'error'

export function useDocument() {
  const [state, setState] = useState<DocumentState>('idle')
  const [deliverables, setDeliverables] = useState<Deliverables | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(
    async (
      intent: DesignIntent,
      analysis: AnalysisResult,
      narrative: NaturalReport,
      geometryArtifacts: CachedArtifacts,
      sessionId: string | null,
    ) => {
      setState('running')
      setError(null)
      setDeliverables(null)
      try {
        const data = await apiPost<Deliverables>('/document', {
          intent,
          analysis_result: analysis,
          natural_report: narrative,
          geometry_artifacts: geometryArtifacts,
          session_id: sessionId,
        })
        setDeliverables(data)
        setState('done')
      } catch (e: unknown) {
        const body = (e as { body?: BackendError }).body
        setError(body ?? { code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, deliverables, error, run }
}
