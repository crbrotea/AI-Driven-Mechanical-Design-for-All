'use client'
import { Suspense, useEffect, useState } from 'react'
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
import { getOrCreateSessionId, setSessionId } from '@/lib/session-storage'
import type { DesignIntent } from '@/lib/types'

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
  const [intent, setIntent] = useState<DesignIntent | null>(null)
  const { state: genState, start: startGen, result, events: genEvents, error: genError } =
    useGenerateStream()
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

  // Hash-only mode: fire a toast when artifacts fail to load (404 / network)
  useEffect(() => {
    if (hashOnlyMode && artifactsError) {
      toast('This design was not found', 'error')
    }
  }, [hashOnlyMode, artifactsError])

  // Hash-only mode: loading state — show spinner, not the 3-col layout
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

  // Hash-only mode: resolved (artifacts loaded) — show viewer only
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

  // Hash-only mode: error (404 or network) — fall through to 3-col layout with toast already fired above

  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <main className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[30%_20%_50%]">
        <ChatPanel
          sessionId={sessionId}
          initialPrompt={initialPrompt}
          onIntentReady={(i) => setIntent(i as DesignIntent)}
        />
        <FormPanel sessionId={sessionId} overrideIntent={intent} onGenerate={onGenerate} />
        <div className="relative flex flex-col">
          {genState === 'generating' && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
              <ProgressStream events={genEvents} />
            </div>
          )}
          {genError && (
            <div className="p-4">
              <ErrorBanner error={genError} onRetry={() => intent && onGenerate(intent, 'steel_a36')} />
            </div>
          )}
          <ViewerPanel result={viewerResult} />
        </div>
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
