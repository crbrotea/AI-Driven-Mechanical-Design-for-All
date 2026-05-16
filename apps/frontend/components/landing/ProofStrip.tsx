'use client'
import { Atom, Download, Layers } from 'lucide-react'
import { useTranslations } from 'next-intl'

const ITEMS = [
  { key: 'formulas', Icon: Atom },
  { key: 'exports', Icon: Download },
  { key: 'materials', Icon: Layers },
] as const

export function ProofStrip() {
  const t = useTranslations('landing.proof')
  return (
    <section className="border-y border-border bg-muted/40" aria-labelledby="proof-title">
      <div className="mx-auto max-w-7xl px-6 py-14">
        <h2
          id="proof-title"
          className="font-display text-2xl font-extrabold tracking-tight md:text-3xl"
        >
          {t('title')}
        </h2>
        <ul className="mt-8 grid gap-6 md:grid-cols-3">
          {ITEMS.map((item) => {
            const Icon = item.Icon
            return (
              <li
                key={item.key}
                className="flex items-start gap-3 rounded-xl border border-border bg-background p-4"
              >
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-brotea-violet" aria-hidden="true" />
                <p className="text-sm text-foreground">{t(`items.${item.key}`)}</p>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
