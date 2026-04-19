import type { SSEEvent } from './types'

export async function* parseSSE(
  reader: ReadableStreamDefaultReader<string>,
): AsyncGenerator<SSEEvent> {
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) return
    buffer += value
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const raw of events) {
      const parsed = parseSingleEvent(raw)
      if (parsed) yield parsed
    }
  }
}

function parseSingleEvent(raw: string): SSEEvent | null {
  const match = raw.match(/^event:\s*(\w+)\ndata:\s*(.*)$/ms)
  if (!match) return null
  try {
    return { event: match[1], data: JSON.parse(match[2]) } as SSEEvent
  } catch {
    return null
  }
}
