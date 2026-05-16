import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '../types'
import { useDocument } from './useDocument'

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
const NARRATIVE: NaturalReport = {
  summary: 'ok', risks: [], suggestions: [], analogies: [], facts_used: ['safety_factor'],
}
const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75, center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://example/step',
  glb_url: 'https://example/glb',
  svg_url: 'https://example/svg',
}

const DELIVERABLES = {
  report_pdf_url: 'https://example/report.pdf',
  drawing_pdf_url: 'https://example/drawing.pdf',
  step_url: 'https://example/step',
  glb_url: 'https://example/glb',
  svg_url: 'https://example/svg',
  cache_hit: false,
  cache_key: 'doc1',
}

describe('useDocument', () => {
  it('sets deliverables on success', async () => {
    server.use(http.post('*/document', () => HttpResponse.json(DELIVERABLES)))
    const { result } = renderHook(() => useDocument())
    await act(async () => {
      await result.current.run(INTENT, ANALYSIS, NARRATIVE, ARTIFACTS, 'sid')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.deliverables?.report_pdf_url).toBe('https://example/report.pdf')
  })

  it('sets error on backend 502', async () => {
    server.use(
      http.post('*/document', () =>
        HttpResponse.json(
          { code: 'gcs_upload_failed', message: 'transient', retry_after: 5 },
          { status: 502 },
        ),
      ),
    )
    const { result } = renderHook(() => useDocument())
    await act(async () => {
      await result.current.run(INTENT, ANALYSIS, NARRATIVE, ARTIFACTS, 'sid')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('gcs_upload_failed')
  })
})
