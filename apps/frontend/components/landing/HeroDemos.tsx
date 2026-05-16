'use client'
import { useTranslations } from 'next-intl'
import { HeroCard } from './HeroCard'

export function HeroDemos() {
  const t = useTranslations('landing.demos')
  return (
    <section className="bg-background" aria-labelledby="demos-title">
      <div className="mx-auto max-w-7xl px-6 py-16 md:py-24">
        <div className="mb-10 max-w-2xl">
          <h2
            id="demos-title"
            className="font-display text-3xl font-extrabold tracking-tight md:text-4xl"
          >
            {t('title')}
          </h2>
          <p className="mt-3 text-base text-muted-foreground md:text-lg">{t('subtitle')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <HeroCard preset="flywheel" />
          <HeroCard preset="hydro" />
          <HeroCard preset="shelter" />
        </div>
      </div>
    </section>
  )
}
