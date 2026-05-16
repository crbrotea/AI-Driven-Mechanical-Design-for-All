'use client'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { useTranslations } from 'next-intl'

export function FooterCTA() {
  const t = useTranslations('landing.footer')
  return (
    <section
      className="bg-primary text-primary-foreground"
      aria-labelledby="footer-cta-title"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-16 md:flex-row md:items-center md:justify-between md:py-20">
        <div className="max-w-xl">
          <h2
            id="footer-cta-title"
            className="font-display text-3xl font-extrabold tracking-tight md:text-4xl"
          >
            {t('title')}
          </h2>
          <p className="mt-2 text-base text-primary-foreground/85 md:text-lg">{t('subtitle')}</p>
        </div>
        <Link
          href="/design"
          className="inline-flex h-12 items-center justify-center gap-2 self-start rounded-md bg-brotea-glow px-8 text-base font-semibold text-brotea-eggplant transition-opacity hover:opacity-90 motion-reduce:transition-none md:self-auto"
        >
          {t('cta')}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}
