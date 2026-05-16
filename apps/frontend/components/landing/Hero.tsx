'use client'
import Image from 'next/image'
import Link from 'next/link'
import { ArrowRight, Sparkles } from 'lucide-react'
import { useTranslations } from 'next-intl'

export function Hero() {
  const t = useTranslations('landing.hero')
  return (
    <section
      className="relative overflow-hidden border-b border-border"
      aria-labelledby="hero-headline"
    >
      <div className="mx-auto grid max-w-7xl gap-12 px-6 py-20 md:py-28 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div className="space-y-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-brotea-violet" aria-hidden="true" />
            {t('eyebrow')}
          </span>
          <h1
            id="hero-headline"
            className="font-display text-5xl font-extrabold leading-[1.04] tracking-tight md:text-6xl lg:text-7xl"
          >
            {t('headline')}
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-muted-foreground md:text-xl">
            {t('subline')}
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href="/design"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-primary px-8 text-base font-semibold text-primary-foreground transition-opacity hover:opacity-90 motion-reduce:transition-none"
            >
              {t('cta')}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              href="/design?preset=flywheel"
              className="inline-flex h-12 items-center justify-center rounded-md border border-border bg-background px-6 text-base font-medium text-foreground transition-colors hover:bg-muted motion-reduce:transition-none"
            >
              {t('cta_secondary')}
            </Link>
          </div>
        </div>
        <div className="relative mx-auto aspect-square w-full max-w-md">
          <div className="absolute inset-0 -z-10 rounded-[48px] bg-brotea-violet/15 blur-3xl" aria-hidden="true" />
          <div className="relative h-full w-full overflow-hidden rounded-[48px] border-2 border-brotea-glow bg-brotea-eggplant p-6 shadow-xl">
            <Image
              src="/logo.png"
              alt=""
              fill
              className="object-contain p-6"
              sizes="(max-width: 768px) 80vw, 480px"
              priority
            />
          </div>
        </div>
      </div>
    </section>
  )
}
