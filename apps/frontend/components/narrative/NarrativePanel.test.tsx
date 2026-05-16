import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../../test/msw/server'
import type { AnalysisResult, DesignIntent } from '../../lib/types'
import { NarrativePanel } from './NarrativePanel'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}
const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'x',
  stress_max_pa: 1,
  displacement_max_m: 1,
  safety_factor: 5,
  verdict: 'pass',
  inputs: {},
}

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('')
}

describe('NarrativePanel', () => {
  it('disables Explain when analysis is null', () => {
    render(<NarrativePanel intent={INTENT} analysis={null} sessionId={null} onReport={vi.fn()} />)
    expect(screen.getByRole('button', { name: /explain/i })).toBeDisabled()
  })

  it('renders structured report after streaming completes', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(
          sseBody([
            { event: 'chunk', data: { text: 'Hello ' } },
            { event: 'chunk', data: { text: 'world.' } },
            {
              event: 'final',
              data: {
                report: {
                  summary: 'Hello world.',
                  risks: ['stress'],
                  suggestions: ['inspect'],
                  analogies: ['like a tiger'],
                  facts_used: ['safety_factor'],
                },
                cache_hit: false,
                cache_key: 'k1',
              },
            },
          ]),
          { headers: { 'Content-Type': 'text/event-stream' } },
        ),
      ),
    )
    const onReport = vi.fn()
    render(
      <NarrativePanel
        intent={INTENT}
        analysis={ANALYSIS}
        sessionId="sid"
        onReport={onReport}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /explain/i }))
    await waitFor(() => expect(screen.getByText('Hello world.')).toBeInTheDocument())
    expect(screen.getByText('stress')).toBeInTheDocument()
    expect(screen.getByText('inspect')).toBeInTheDocument()
    expect(screen.getByText('like a tiger')).toBeInTheDocument()
    expect(screen.getByText(/safety_factor/)).toBeInTheDocument()
    expect(onReport).toHaveBeenCalled()
  })
})
