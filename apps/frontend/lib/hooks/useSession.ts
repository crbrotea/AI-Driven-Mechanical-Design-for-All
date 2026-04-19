import useSWR from 'swr'
import { apiGet } from '@/lib/api-client'
import type { Session } from '@/lib/types'

export function useSession(sessionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<{ session: Session }>(
    sessionId ? `/interpret/sessions/${sessionId}` : null,
    apiGet,
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  return {
    session: data?.session ?? null,
    error,
    isLoading,
    mutate,
  }
}
