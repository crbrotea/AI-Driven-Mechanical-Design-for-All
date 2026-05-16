import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '../../lib/types'
import { DeliverablesPanel } from './DeliverablesPanel'

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
  summary: 'ok', risks: [], suggestions: [], analogies: [], facts_used: [],
}
const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75,
    center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://example.com/step',
  glb_url: 'https://example.com/glb',
  svg_url: 'https://example.com/svg',
}

describe('DeliverablesPanel', () => {
  it('disables button until all prerequisites are present', () => {
    render(
      <DeliverablesPanel
        intent={null}
        analysis={null}
        narrative={null}
        geometryArtifacts={null}
        sessionId={null}
      />,
    )
    expect(screen.getByRole('button', { name: /generate documents/i })).toBeDisabled()
  })

  it('renders 5 links and an iframe preview after success', async () => {
    server.use(
      http.post('*/document', () =>
        HttpResponse.json({
          report_pdf_url: 'https://example.com/report.pdf',
          drawing_pdf_url: 'https://example.com/drawing.pdf',
          step_url: 'https://example.com/step',
          glb_url: 'https://example.com/glb',
          svg_url: 'https://example.com/svg',
          cache_hit: false,
          cache_key: 'doc1',
        }),
      ),
    )
    render(
      <DeliverablesPanel
        intent={INTENT}
        analysis={ANALYSIS}
        narrative={NARRATIVE}
        geometryArtifacts={ARTIFACTS}
        sessionId="sid"
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /generate documents/i }))
    await waitFor(() => expect(screen.getByText('Report PDF')).toBeInTheDocument())
    expect(screen.getByText('Drawing PDF')).toBeInTheDocument()
    expect(screen.getByText('STEP')).toBeInTheDocument()
    expect(screen.getByText('GLB')).toBeInTheDocument()
    expect(screen.getByText('SVG section')).toBeInTheDocument()
    expect(screen.getByTitle(/report preview/i)).toBeInTheDocument()
  })
})
