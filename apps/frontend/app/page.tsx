'use client'
import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { HeroCard } from '@/components/landing/HeroCard'
import { Topbar } from '@/components/shared/Topbar'

export default function Landing() {
  const t = useTranslations('landing.hero')
  return (
    <>
      <Topbar />
      <main className="mx-auto max-w-5xl px-4 py-16">
        <section className="text-center">
          <h1 className="text-4xl font-bold md:text-5xl">{t('headline')}</h1>
          <p className="mt-4 text-lg text-muted-foreground">{t('subline')}</p>
          <Link
            href="/design"
            className="mt-8 inline-flex h-12 items-center justify-center rounded-md bg-primary px-8 text-base font-medium text-primary-foreground hover:opacity-90"
          >
            {t('cta')}
          </Link>
        </section>
        <section className="mt-16 grid grid-cols-1 gap-4 md:grid-cols-3">
          <HeroCard preset="flywheel" />
          <HeroCard preset="hydro" />
          <HeroCard preset="shelter" />
        </section>
      </main>
    </>
  )
}
