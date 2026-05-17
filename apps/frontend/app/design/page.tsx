'use client'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import dynamic from 'next/dynamic'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { FormPanel } from '@/components/form/FormPanel'
import { Topbar } from '@/components/shared/Topbar'
import { ToastContainer, toast } from '@/components/ui/toast'
import { ProgressStream } from '@/components/shared/ProgressStream'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { useGenerateStream } from '@/lib/hooks/useGenerateStream'
import { useArtifacts } from '@/lib/hooks/useArtifacts'
import { useIntent } from '@/lib/hooks/useIntent'
import { getOrCreateSessionId, setSessionId } from '@/lib/session-storage'
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { NarrativePanel } from '@/components/narrative/NarrativePanel'
import { DeliverablesPanel } from '@/components/deliverables/DeliverablesPanel'
import { Stepper, type StepperState } from '@/components/design/Stepper'
import { PartsBom } from '@/components/design/PartsBom'
import { PipelineTabs, type TabDef } from '@/components/design/PipelineTabs'
import type { AnalysisResult, DesignIntent, NaturalReport } from '@/lib/types'

const ViewerPanel = dynamic(
  () => import('@/components/viewer/ViewerPanel').then((m) => m.ViewerPanel),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
        Loading viewer...
      </div>
    ),
  },
)

const PRESET_PROMPTS: Record<string, string> = {
  flywheel: 'Design a flywheel storing 500 kJ at 3000 RPM',
  hydro: 'Design a hydroelectric generator for 5 m³/s at 20m head',
  shelter: 'A foldable shelter for 4 people, withstanding 100 km/h winds',
}

function DesignPageInner() {
  const router = useRouter()
  const params = useSearchParams()
  const preset = params.get('preset')
  const hashParam = params.get('hash')
  const sidParam = params.get('session_id')

  const [sessionId, setSid] = useState<string | null>(null)
  const [chatIntent, setChatIntent] = useState<DesignIntent | null>(null)
  const { intent: sessionIntent } = useIntent(sessionId)
  // Prefer the session-backed intent — it reflects every refine call. Fall
  // back to the chat snapshot only when the session hasn't hydrated yet.
  const intent = sessionIntent ?? chatIntent
  const [materialName, setMaterialName] = useState<string>('steel_a36')
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [narrative, setNarrative] = useState<NaturalReport | null>(null)
  const [hasDeliverables, setHasDeliverables] = useState(false)
  const { state: genState, start: startGen, result, events: genEvents, error: genError } =
    useGenerateStream()
  const geometryArtifacts = result
    ? {
        mass_properties: result.mass_properties,
        step_url: result.artifacts.step_url,
        glb_url: result.artifacts.glb_url,
        svg_url: result.artifacts.svg_url,
      }
    : null
  const { artifacts: cachedArtifacts, error: artifactsError, isLoading: artifactsLoading } =
    useArtifacts(hashParam)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (sidParam) {
      setSessionId(sidParam)
      setSid(sidParam)
    } else {
      const id = getOrCreateSessionId()
      setSid(id)
      const url = new URLSearchParams(params.toString())
      url.set('session_id', id)
      router.replace(`/design?${url.toString()}`)
    }
  }, [])

  const initialPrompt = preset ? PRESET_PROMPTS[preset] ?? '' : ''

  async function onGenerate(i: DesignIntent, material: string) {
    await startGen(i, material, sessionId)
  }

  const hashOnlyMode = Boolean(hashParam)
  const viewerResult = result ?? cachedArtifacts
  const totalMassKg = result?.mass_properties?.mass_kg ?? cachedArtifacts?.mass_properties?.mass_kg ?? null

  const stepperState: StepperState = useMemo(
    () => ({
      describe: intent != null,
      configure: intent != null && (result != null || cachedArtifacts != null),
      build: result != null || cachedArtifacts != null,
      validate: analysis != null,
      ship: hasDeliverables,
    }),
    [intent, result, cachedArtifacts, analysis, hasDeliverables],
  )

  const tabs: TabDef[] = [
    { key: 'parameters', available: intent != null },
    { key: 'analysis', available: intent != null && (result != null || cachedArtifacts != null), badge: analysis?.verdict.toUpperCase() },
    { key: 'narrative', available: analysis != null },
    { key: 'deliverables', available: narrative != null },
  ]

  // Hash-only mode: fire a toast when artifacts fail to load (404 / network)
  useEffect(() => {
    if (hashOnlyMode && artifactsError) {
      toast('This design was not found', 'error')
    }
  }, [hashOnlyMode, artifactsError])

  if (hashOnlyMode && artifactsLoading && !cachedArtifacts && !artifactsError) {
    return (
      <div className="flex h-screen flex-col">
        <Topbar />
        <main className="flex flex-1 items-center justify-center">
          <div className="text-sm text-muted-foreground">Loading design...</div>
        </main>
        <ToastContainer />
      </div>
    )
  }

  if (hashOnlyMode && cachedArtifacts) {
    return (
      <div className="flex h-screen flex-col">
        <Topbar />
        <main className="flex-1">
          <ViewerPanel result={viewerResult} />
        </main>
        <ToastContainer />
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <Stepper state={stepperState} />
      <main className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <ChatPanel
          sessionId={sessionId}
          initialPrompt={initialPrompt}
          onIntentReady={(i) => setChatIntent(i as DesignIntent)}
        />
        <div className="relative flex flex-col overflow-hidden">
          <div className="relative flex-1 min-h-0">
            {genState === 'generating' && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
                <ProgressStream events={genEvents} />
              </div>
            )}
            {genError && (
              <div className="absolute inset-x-4 top-4 z-10">
                <ErrorBanner error={genError} onRetry={() => intent && onGenerate(intent, materialName)} />
              </div>
            )}
            <ViewerPanel result={viewerResult} />
          </div>
          <div className="h-[42%] min-h-[280px] shrink-0 border-t border-border bg-background">
            <PipelineTabs tabs={tabs} defaultTab="parameters">
              {(active) => {
                if (active === 'parameters') {
                  return (
                    <FormPanel
                      sessionId={sessionId}
                      overrideIntent={intent}
                      onGenerate={onGenerate}
                      onMaterialChange={setMaterialName}
                    />
                  )
                }
                if (active === 'analysis') {
                  return (
                    <AnalysisPanel
                      intent={intent}
                      materialName={materialName}
                      onResult={setAnalysis}
                    />
                  )
                }
                if (active === 'narrative') {
                  return (
                    <NarrativePanel
                      intent={intent}
                      analysis={analysis}
                      sessionId={sessionId}
                      onReport={setNarrative}
                    />
                  )
                }
                if (active === 'deliverables') {
                  return (
                    <DeliverablesPanel
                      intent={intent}
                      analysis={analysis}
                      narrative={narrative}
                      geometryArtifacts={geometryArtifacts}
                      sessionId={sessionId}
                      onDelivered={() => setHasDeliverables(true)}
                    />
                  )
                }
                return null
              }}
            </PipelineTabs>
          </div>
        </div>
        <PartsBom intent={intent} materialName={materialName} totalMassKg={totalMassKg} />
      </main>
      <ToastContainer />
    </div>
  )
}

export default function DesignPage() {
  return (
    <Suspense fallback={<div className="p-8">Loading...</div>}>
      <DesignPageInner />
    </Suspense>
  )
}
