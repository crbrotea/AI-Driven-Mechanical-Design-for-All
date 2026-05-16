'use client'
import Link from 'next/link'
import { ArrowUpRight, Boxes, Disc3, Tent } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Card } from '@/components/ui/card'

const ICONS = {
  flywheel: Disc3,
  hydro: Boxes,
  shelter: Tent,
} as const

export function HeroCard({ preset }: { preset: 'flywheel' | 'hydro' | 'shelter' }) {
  const t = useTranslations('landing.heroes')
  const Icon = ICONS[preset]
  return (
    <Link
      href={`/design?preset=${preset}`}
      className="group block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-2xl"
    >
      <Card className="h-full rounded-2xl border border-border bg-background p-6 transition-colors hover:border-brotea-violet motion-reduce:transition-none">
        <div className="flex items-start justify-between gap-4">
          <Icon className="h-7 w-7 text-brotea-violet" aria-hidden="true" />
          <ArrowUpRight
            className="h-5 w-5 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transform-none"
            aria-hidden="true"
          />
        </div>
        <h3 className="mt-6 font-display text-xl font-bold tracking-tight">
          {t(`${preset}.title`)}
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">{t(`${preset}.subtitle`)}</p>
      </Card>
    </Link>
  )
}
