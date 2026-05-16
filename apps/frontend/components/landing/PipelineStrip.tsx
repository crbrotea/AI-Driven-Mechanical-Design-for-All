'use client'
import { Cpu, FileText, Layers, MessageSquare, Wrench } from 'lucide-react'
import { useTranslations } from 'next-intl'

const STEPS = [
  { key: 'interpret', Icon: MessageSquare },
  { key: 'geometry', Icon: Layers },
  { key: 'physics', Icon: Cpu },
  { key: 'explain', Icon: Wrench },
  { key: 'document', Icon: FileText },
] as const

export function PipelineStrip() {
  const t = useTranslations('landing.pipeline')
  return (
    <section
      className="bg-brotea-eggplant text-brotea-bone"
      aria-labelledby="pipeline-title"
    >
      <div className="mx-auto max-w-7xl px-6 py-16 md:py-24">
        <div className="mb-12 max-w-2xl">
          <h2
            id="pipeline-title"
            className="font-display text-3xl font-extrabold tracking-tight md:text-4xl"
          >
            {t('title')}
          </h2>
          <p className="mt-3 text-base text-brotea-bone/70 md:text-lg">{t('subtitle')}</p>
        </div>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((step, i) => {
            const Icon = step.Icon
            return (
              <li
                key={step.key}
                className="group relative flex flex-col gap-3 rounded-2xl border border-brotea-bone/15 bg-brotea-bone/[0.04] p-5 transition-colors hover:border-brotea-glow motion-reduce:transition-none"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-brotea-glow">0{i + 1}</span>
                  <Icon className="h-5 w-5 text-brotea-glow" aria-hidden="true" />
                </div>
                <h3 className="font-display text-lg font-bold tracking-tight">
                  {t(`steps.${step.key}.title`)}
                </h3>
                <p className="text-sm text-brotea-bone/70">{t(`steps.${step.key}.subtitle`)}</p>
              </li>
            )
          })}
        </ol>
      </div>
    </section>
  )
}
