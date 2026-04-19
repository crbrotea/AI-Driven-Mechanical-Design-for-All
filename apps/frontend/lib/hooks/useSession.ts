import { z } from 'zod'
import useSWR from 'swr'
import { apiGet } from '@/lib/api-client'
import { SessionSchema } from '@/lib/schemas'
import type { Session } from '@/lib/types'

const SessionResponseSchema = z.object({ session: SessionSchema })

function fetcher(path: string): Promise<{ session: Session }> {
  return apiGet<{ session: Session }>(path, SessionResponseSchema)
}

export function useSession(sessionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<{ session: Session }>(
    sessionId ? `/interpret/sessions/${sessionId}` : null,
    fetcher,
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  return {
    session: data?.session ?? null,
    error,
    isLoading,
    mutate,
  }
}
