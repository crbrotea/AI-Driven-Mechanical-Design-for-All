import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../../test/msw/server'
import type { DesignIntent } from '../../lib/types'
import { AnalysisPanel } from './AnalysisPanel'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

describe('AnalysisPanel', () => {
  it('disables the button when intent is null', () => {
    render(<AnalysisPanel intent={null} materialName="steel_a36" onResult={vi.fn()} />)
    expect(screen.getByRole('button', { name: /analyze/i })).toBeDisabled()
  })

  it('shows verdict and SF after clicking Analyze', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json({
          intent_type: 'Flywheel_Rim',
          material_name: 'steel_a36',
          material_yield_mpa: 250,
          formula: 'sigma = rho*omega^2*R^2',
          stress_max_pa: 4.84e7,
          displacement_max_m: 6e-5,
          safety_factor: 5.16,
          verdict: 'pass',
          inputs: {},
          notes: null,
        }),
      ),
    )
    const onResult = vi.fn()
    render(<AnalysisPanel intent={INTENT} materialName="steel_a36" onResult={onResult} />)
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText('PASS')).toBeInTheDocument())
    expect(screen.getByText(/SF = 5\.16/)).toBeInTheDocument()
    expect(screen.getByText('sigma = rho*omega^2*R^2')).toBeInTheDocument()
    await waitFor(() => expect(onResult).toHaveBeenCalled())
  })

  it('shows error message when backend returns 422', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'invalid_input', message: 'unknown material', field: 'material_name' },
          { status: 422 },
        ),
      ),
    )
    render(<AnalysisPanel intent={INTENT} materialName="x" onResult={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText(/unknown material/)).toBeInTheDocument())
  })
})
