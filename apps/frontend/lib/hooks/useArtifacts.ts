import useSWR from 'swr'
import { apiGet } from '@/lib/api-client'
import type { GenerateResponse } from '@/lib/types'

export function useArtifacts(hash: string | null) {
  const { data, error, isLoading } = useSWR<GenerateResponse>(
    hash ? `/generate/artifacts/${hash}` : null,
    apiGet,
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  return { artifacts: data ?? null, error, isLoading }
}
