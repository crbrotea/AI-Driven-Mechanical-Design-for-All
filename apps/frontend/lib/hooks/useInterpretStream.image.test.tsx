import { describe, it, expect } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { useInterpretStream } from './useInterpretStream'

describe('useInterpretStream — image payload', () => {
  it('omits image fields when no attachment is passed', async () => {
    let captured: Record<string, unknown> | null = null
    server.use(
      http.post('*/interpret', async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>
        return new HttpResponse('event: final\ndata: {"session_id":"x","intent":{"type":"Shaft","fields":{}},"language":"en"}\n\n', {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )

    const { result } = renderHook(() => useInterpretStream())
    await act(async () => {
      await result.current.start('hello', 'sid')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))

    expect(captured).not.toBeNull()
    expect(captured!.prompt).toBe('hello')
    expect(captured!).not.toHaveProperty('image_b64')
    expect(captured!).not.toHaveProperty('image_mime')
  })

  it('sends image_b64 + image_mime when attachment is passed', async () => {
    let captured: Record<string, unknown> | null = null
    server.use(
      http.post('*/interpret', async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>
        return new HttpResponse('event: final\ndata: {"session_id":"x","intent":{"type":"Shaft","fields":{}},"language":"en"}\n\n', {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )

    const { result } = renderHook(() => useInterpretStream())
    await act(async () => {
      await result.current.start('use this sketch', 'sid', {
        b64: 'iVBORw0KGgo=',
        mime: 'image/png',
      })
    })
    await waitFor(() => expect(result.current.state).toBe('done'))

    expect(captured).not.toBeNull()
    expect(captured!.prompt).toBe('use this sketch')
    expect(captured!.image_b64).toBe('iVBORw0KGgo=')
    expect(captured!.image_mime).toBe('image/png')
  })
})
