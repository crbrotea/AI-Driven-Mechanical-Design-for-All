'use client'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useDocument } from '@/lib/hooks/useDocument'
import { PdfPreview } from './PdfPreview'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export interface DeliverablesPanelProps {
  intent: DesignIntent | null
  analysis: AnalysisResult | null
  narrative: NaturalReport | null
  geometryArtifacts: CachedArtifacts | null
  sessionId: string | null
}

export function DeliverablesPanel({
  intent,
  analysis,
  narrative,
  geometryArtifacts,
  sessionId,
}: DeliverablesPanelProps) {
  const { state, deliverables, error, run } = useDocument()
  const ready = Boolean(intent && analysis && narrative && geometryArtifacts)

  const handleClick = () => {
    if (intent && analysis && narrative && geometryArtifacts) {
      void run(intent, analysis, narrative, geometryArtifacts, sessionId)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-base font-bold tracking-tight">Deliverables</h2>
        <Button
          size="sm"
          disabled={!ready || state === 'running'}
          onClick={handleClick}
        >
          {state === 'running' ? 'Packaging…' : 'Generate documents'}
        </Button>
      </div>
      {error && (
        <div role="alert" className="text-xs text-danger">
          {error.message}
          {typeof error.retry_after === 'number' && (
            <span className="ml-2 text-muted-foreground">
              retry in {error.retry_after}s
            </span>
          )}
        </div>
      )}
      {deliverables && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <a href={deliverables.report_pdf_url} target="_blank" rel="noopener" className="text-xs underline">
              Report PDF
            </a>
            <a href={deliverables.drawing_pdf_url} target="_blank" rel="noopener" className="text-xs underline">
              Drawing PDF
            </a>
            <a href={deliverables.step_url} target="_blank" rel="noopener" className="text-xs underline">
              STEP
            </a>
            <a href={deliverables.glb_url} target="_blank" rel="noopener" className="text-xs underline">
              GLB
            </a>
            <a href={deliverables.svg_url} target="_blank" rel="noopener" className="text-xs underline col-span-2">
              SVG section
            </a>
          </div>
          <PdfPreview url={deliverables.report_pdf_url} title="report preview" />
        </div>
      )}
    </Card>
  )
}
