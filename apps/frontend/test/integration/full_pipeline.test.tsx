import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { NarrativePanel } from '@/components/narrative/NarrativePanel'
import { DeliverablesPanel } from '@/components/deliverables/DeliverablesPanel'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'
import { useState } from 'react'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75,
    center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://mock/step',
  glb_url: '/mock.glb',
  svg_url: 'https://mock/svg',
}

function Harness() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [narrative, setNarrative] = useState<NaturalReport | null>(null)
  return (
    <div>
      <AnalysisPanel intent={INTENT} materialName="steel_a36" onResult={setAnalysis} />
      <NarrativePanel
        intent={INTENT}
        analysis={analysis}
        sessionId="sid"
        onReport={setNarrative}
      />
      <DeliverablesPanel
        intent={INTENT}
        analysis={analysis}
        narrative={narrative}
        geometryArtifacts={ARTIFACTS}
        sessionId="sid"
      />
    </div>
  )
}

describe('full pipeline integration (panels stacked, msw default handlers)', () => {
  it('cascades intent → analysis → narrative → deliverables', async () => {
    render(<Harness />)

    // 1. Analyze
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText('PASS')).toBeInTheDocument())

    // 2. Explain — now enabled because analysis state set
    const explainBtn = await screen.findByRole('button', { name: /^explain$/i })
    expect(explainBtn).toBeEnabled()
    await userEvent.click(explainBtn)
    await waitFor(() =>
      expect(
        screen.getByText('The flywheel is well below the yield limit.'),
      ).toBeInTheDocument(),
    )

    // 3. Generate documents — now enabled because narrative state set
    const docBtn = await screen.findByRole('button', { name: /generate documents/i })
    await waitFor(() => expect(docBtn).toBeEnabled())
    await userEvent.click(docBtn)
    await waitFor(() => expect(screen.getByText('Report PDF')).toBeInTheDocument())
    expect(screen.getByTitle(/report preview/i)).toBeInTheDocument()
  })
})
