import type { ZodType } from 'zod'
import type { SSEEvent } from './types'
import { parseSSE } from './sse-parser'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`HTTP ${status}`)
  }
}

export async function apiGet<T>(path: string, schema?: ZodType<T>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'omit' })
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null))
  const body = await res.json()
  return schema ? schema.parse(body) : (body as T)
}

export async function apiPost<T>(path: string, body: unknown, schema?: ZodType<T>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null))
  const data = await res.json()
  return schema ? schema.parse(data) : (data as T)
}

export async function* apiStream(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null))
  if (!res.body) throw new Error('Response has no body')
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  yield* parseSSE(reader)
}
