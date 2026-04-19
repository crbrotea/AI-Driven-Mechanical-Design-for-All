import useSWR from 'swr'
import { apiGet } from '@/lib/api-client'
import { GenerateResponseSchema } from '@/lib/schemas'
import type { GenerateResponse } from '@/lib/types'

function fetcher(path: string): Promise<GenerateResponse> {
  return apiGet<GenerateResponse>(path, GenerateResponseSchema)
}

export function useArtifacts(hash: string | null) {
  const { data, error, isLoading } = useSWR<GenerateResponse>(
    hash ? `/generate/artifacts/${hash}` : null,
    fetcher,
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  return { artifacts: data ?? null, error, isLoading }
}
