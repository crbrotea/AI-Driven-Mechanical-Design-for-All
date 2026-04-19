'use client'
import { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, Grid, Html, useProgress } from '@react-three/drei'
import { useTranslations } from 'next-intl'
import type { GenerateResponse } from '@/lib/types'
import { ModelMesh } from './ModelMesh'
import { ViewerControls } from './ViewerControls'
import { MassPanel } from './MassPanel'

function LoadingFallback() {
  const { progress } = useProgress()
  return (
    <Html center>
      <div className="rounded bg-black/60 px-3 py-1 text-white">Loading 3D... {progress.toFixed(0)}%</div>
    </Html>
  )
}

export function ViewerPanel({ result }: { result: GenerateResponse | null }) {
  const t = useTranslations('viewer')

  if (!result) {
    return (
      <section className="flex h-full items-center justify-center text-sm text-muted-foreground" aria-label="3D viewer">
        {t('placeholder')}
      </section>
    )
  }

  return (
    <section className="relative flex h-full flex-col" aria-label="3D viewer">
      <figcaption className="sr-only">
        3D model: mass {result.mass_properties.mass_kg.toFixed(1)} kg
      </figcaption>
      <Canvas shadows camera={{ position: [2, 1.5, 2], fov: 45 }} className="flex-1">
        <Suspense fallback={<LoadingFallback />}>
          <Environment preset="studio" />
          <ambientLight intensity={0.3} />
          <directionalLight position={[5, 5, 5]} castShadow intensity={1} />
          <Grid infiniteGrid cellSize={0.1} sectionSize={1} />
          <ModelMesh glbUrl={result.artifacts.glb_url} />
          <OrbitControls makeDefault enableDamping />
        </Suspense>
      </Canvas>
      <ViewerControls stepUrl={result.artifacts.step_url} glbUrl={result.artifacts.glb_url} />
      <MassPanel properties={result.mass_properties} />
    </section>
  )
}
