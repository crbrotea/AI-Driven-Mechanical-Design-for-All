import { describe, it, expect } from 'vitest'
import { parseSSE } from './sse-parser'

function mockReader(chunks: string[] | string) {
  const arr = Array.isArray(chunks) ? chunks : [chunks]
  let i = 0
  return {
    async read() {
      if (i >= arr.length) return { done: true, value: undefined }
      return { done: false, value: arr[i++] }
    },
  } as unknown as ReadableStreamDefaultReader<string>
}

async function collectAll<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = []
  for await (const e of gen) out.push(e)
  return out
}

describe('parseSSE', () => {
  it('parses a single event', async () => {
    const reader = mockReader('event: progress\ndata: {"pct":20}\n\n')
    const events = await collectAll(parseSSE(reader))
    expect(events).toEqual([{ event: 'progress', data: { pct: 20 } }])
  })

  it('parses multiple events in one chunk', async () => {
    const reader = mockReader('event: a\ndata: {"x":1}\n\nevent: b\ndata: {"y":2}\n\n')
    const events = await collectAll(parseSSE(reader))
    expect(events).toHaveLength(2)
  })

  it('handles events split across chunks', async () => {
    const reader = mockReader(['event: progress\n', 'data: {"pct":50}\n\n'])
    const events = await collectAll(parseSSE(reader))
    expect(events).toHaveLength(1)
  })

  it('ignores malformed events', async () => {
    const reader = mockReader('malformed\n\n')
    const events = await collectAll(parseSSE(reader))
    expect(events).toEqual([])
  })
})
