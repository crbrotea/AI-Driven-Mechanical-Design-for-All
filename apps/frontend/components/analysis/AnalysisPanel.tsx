'use client'
import { useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAnalyze } from '@/lib/hooks/useAnalyze'
import type { AnalysisResult, DesignIntent } from '@/lib/types'

const VERDICT_COLOR: Record<string, string> = {
  pass: 'bg-success text-success-foreground',
  warn: 'bg-warning text-warning-foreground',
  fail: 'bg-danger text-danger-foreground',
}

export interface AnalysisPanelProps {
  intent: DesignIntent | null
  materialName: string
  onResult: (r: AnalysisResult) => void
}

export function AnalysisPanel({ intent, materialName, onResult }: AnalysisPanelProps) {
  const { state, result, error, run } = useAnalyze()

  useEffect(() => {
    if (result) onResult(result)
  }, [result, onResult])

  const handleClick = () => {
    if (intent) void run(intent, materialName)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-base font-bold tracking-tight">Structural Analysis</h2>
        <Button
          size="sm"
          disabled={!intent || state === 'running'}
          onClick={handleClick}
        >
          {state === 'running' ? 'Analyzing…' : 'Analyze'}
        </Button>
      </div>
      {error && (
        <div role="alert" className="text-xs text-danger">
          {error.field && <span className="font-mono mr-1">[{error.field}]</span>}
          {error.message}
        </div>
      )}
      {result && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 text-xs font-bold rounded ${
                VERDICT_COLOR[result.verdict] ?? 'bg-muted text-foreground'
              }`}
            >
              {result.verdict.toUpperCase()}
            </span>
            <span className="text-sm">SF = {result.safety_factor.toFixed(2)}</span>
          </div>
          <dl className="text-xs grid grid-cols-2 gap-1">
            <dt className="text-muted-foreground">Stress max</dt>
            <dd>{(result.stress_max_pa / 1e6).toFixed(2)} MPa</dd>
            <dt className="text-muted-foreground">Yield</dt>
            <dd>{result.material_yield_mpa.toFixed(1)} MPa</dd>
            <dt className="text-muted-foreground">Displacement</dt>
            <dd>{(result.displacement_max_m * 1000).toFixed(3)} mm</dd>
          </dl>
          <code className="block text-xs bg-muted/50 px-2 py-1 rounded">
            {result.formula}
          </code>
        </div>
      )}
    </Card>
  )
}
