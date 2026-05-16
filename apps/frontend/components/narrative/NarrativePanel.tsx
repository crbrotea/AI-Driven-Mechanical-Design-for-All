'use client'
import { useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useExplainStream } from '@/lib/hooks/useExplainStream'
import { StreamingText } from './StreamingText'
import type { AnalysisResult, DesignIntent, NaturalReport } from '@/lib/types'

export interface NarrativePanelProps {
  intent: DesignIntent | null
  analysis: AnalysisResult | null
  sessionId: string | null
  onReport: (r: NaturalReport) => void
}

export function NarrativePanel({
  intent,
  analysis,
  sessionId,
  onReport,
}: NarrativePanelProps) {
  const { state, streamedText, report, error, start } = useExplainStream()
  const ready = Boolean(intent && analysis)

  useEffect(() => {
    if (report) onReport(report)
  }, [report, onReport])

  const handleClick = () => {
    if (intent && analysis) void start(intent, analysis, sessionId)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Engineering Narrative</h2>
        <Button
          size="sm"
          disabled={!ready || state === 'streaming'}
          onClick={handleClick}
        >
          {state === 'streaming' ? 'Explaining…' : 'Explain'}
        </Button>
      </div>
      {error && (
        <div className="text-xs text-red-600">{error.message}</div>
      )}
      {state === 'streaming' && streamedText && !report && (
        <StreamingText text={streamedText} />
      )}
      {report && (
        <div className="space-y-2 text-sm">
          <p>{report.summary}</p>
          {report.risks.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Risks</h3>
              <ul className="text-xs list-disc pl-4">
                {report.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {report.suggestions.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Suggestions</h3>
              <ul className="text-xs list-disc pl-4">
                {report.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {report.analogies.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Analogies</h3>
              <ul className="text-xs list-disc pl-4">
                {report.analogies.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-[10px] text-muted-foreground mt-2">
            Facts cited: {report.facts_used.join(', ')}
          </div>
        </div>
      )}
    </Card>
  )
}
