import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type { DesignIntent } from '../types'
import { useAnalyze } from './useAnalyze'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: {
    outer_diameter_m: { value: 0.5, source: 'extracted' },
    inner_diameter_m: { value: 0.1, source: 'extracted' },
    thickness_m: { value: 0.05, source: 'extracted' },
    rpm: { value: 3000, source: 'extracted' },
  },
  composed_of: [],
}

const ANALYSIS_RESULT = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'sigma = rho*omega^2*R^2',
  stress_max_pa: 4.84e7,
  displacement_max_m: 6e-5,
  safety_factor: 5.16,
  verdict: 'pass',
  inputs: { angular_velocity_rad_s: 314.16 },
  notes: null,
}

describe('useAnalyze', () => {
  it('transitions idle -> running -> done and sets result', async () => {
    server.use(http.post('*/analyze', () => HttpResponse.json(ANALYSIS_RESULT)))
    const { result } = renderHook(() => useAnalyze())
    expect(result.current.state).toBe('idle')
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.result?.verdict).toBe('pass')
    expect(result.current.result?.safety_factor).toBe(5.16)
  })

  it('transitions idle -> running -> error on 422', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'invalid_input', message: 'bad', field: 'material_name' },
          { status: 422 },
        ),
      ),
    )
    const { result } = renderHook(() => useAnalyze())
    await act(async () => {
      await result.current.run(INTENT, 'unobtanium')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('invalid_input')
    expect(result.current.error?.field).toBe('material_name')
  })

  it('clears prior result when run is called again', async () => {
    server.use(http.post('*/analyze', () => HttpResponse.json(ANALYSIS_RESULT)))
    const { result } = renderHook(() => useAnalyze())
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'unknown', message: 'boom' },
          { status: 500 },
        ),
      ),
    )
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.result).toBeNull()
  })
})
