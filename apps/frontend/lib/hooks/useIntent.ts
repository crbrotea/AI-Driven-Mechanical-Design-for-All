import { z } from 'zod'
import { apiPost } from '@/lib/api-client'
import { DesignIntentSchema } from '@/lib/schemas'
import { useSession } from './useSession'
import type { DesignIntent, TriStateField } from '@/lib/types'

const RefineResponseSchema = z.object({ intent: DesignIntentSchema })

export function useIntent(sessionId: string | null) {
  const { session, isLoading, error, mutate } = useSession(sessionId)
  const intent = session?.current_intent ?? null

  async function refineIntent(fieldUpdates: Record<string, unknown>): Promise<DesignIntent> {
    if (!sessionId) throw new Error('no session')
    const { intent: next } = await apiPost<{ intent: DesignIntent }>(
      '/interpret/refine',
      { session_id: sessionId, field_updates: fieldUpdates },
      RefineResponseSchema,
    )
    await mutate()
    return next
  }

  const hasMissingFields = Boolean(
    intent &&
      Object.values(intent.fields).some(
        (f) => (f as TriStateField).source === 'missing',
      ),
  )

  return { intent, hasMissingFields, refineIntent, isLoading, error }
}
