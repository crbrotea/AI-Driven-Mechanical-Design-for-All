'use client'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/lib/stores/uiStore'

export function ViewerControls({
  stepUrl,
  glbUrl,
}: {
  stepUrl: string
  glbUrl: string
}) {
  const t = useTranslations('viewer')
  const wireframe = useUIStore((s) => s.viewerWireframe)
  const setWireframe = useUIStore((s) => s.setViewerWireframe)

  return (
    <div className="absolute right-4 top-4 flex gap-2">
      <Button size="sm" variant={wireframe ? 'default' : 'outline'} onClick={() => setWireframe(!wireframe)}>
        {t('wireframe')}
      </Button>
      <a
        href={stepUrl}
        download
        className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-background px-3 text-xs font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {t('download_step')}
      </a>
      <a
        href={glbUrl}
        download
        className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-background px-3 text-xs font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {t('download_glb')}
      </a>
    </div>
  )
}
