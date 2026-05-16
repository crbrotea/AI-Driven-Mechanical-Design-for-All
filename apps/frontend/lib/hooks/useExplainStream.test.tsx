import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type { AnalysisResult, DesignIntent } from '../types'
import { useExplainStream } from './useExplainStream'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'sigma = rho*omega^2*R^2',
  stress_max_pa: 4.84e7,
  displacement_max_m: 6e-5,
  safety_factor: 5.16,
  verdict: 'pass',
  inputs: {},
}

const SSE_OK = [
  { event: 'chunk', data: { text: 'The ' } },
  { event: 'chunk', data: { text: 'flywheel ' } },
  { event: 'chunk', data: { text: 'looks good.' } },
  {
    event: 'final',
    data: {
      report: {
        summary: 'The flywheel looks good.',
        risks: [],
        suggestions: [],
        analogies: [],
        facts_used: ['safety_factor'],
      },
      cache_hit: false,
      cache_key: 'abc',
    },
  },
]

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('')
}

describe('useExplainStream', () => {
  it('accumulates chunk text and emits final report', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(sseBody(SSE_OK), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )
    const { result } = renderHook(() => useExplainStream())
    await act(async () => {
      await result.current.start(INTENT, ANALYSIS, 'sid-1')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.streamedText).toBe('The flywheel looks good.')
    expect(result.current.report?.summary).toBe('The flywheel looks good.')
    expect(result.current.report?.facts_used).toEqual(['safety_factor'])
  })

  it('transitions to error when SSE emits an error event', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(
          sseBody([
            { event: 'progress', data: { step: 'generating' } },
            {
              event: 'error',
              data: { code: 'gemma_timeout', message: 'slow', retry_after: 5 },
            },
          ]),
          { headers: { 'Content-Type': 'text/event-stream' } },
        ),
      ),
    )
    const { result } = renderHook(() => useExplainStream())
    await act(async () => {
      await result.current.start(INTENT, ANALYSIS, 'sid-1')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('gemma_timeout')
  })
})
