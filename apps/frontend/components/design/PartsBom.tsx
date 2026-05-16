'use client'
import { Boxes, Cog, Disc3, Eye, EyeOff, LayoutGrid, Layers, Tent, type LucideIcon, Cylinder } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'
import { apportionMass, derivePartsFromIntent, formatDimensions, type PartSummary } from '@/lib/parts'
import type { DesignIntent } from '@/lib/types'

const PART_ICON: Record<string, LucideIcon> = {
  Flywheel_Rim: Disc3,
  Shaft: Cylinder,
  Bearing_Housing: Cog,
  Pelton_Runner: Disc3,
  Housing: Boxes,
  Mounting_Frame: LayoutGrid,
  Hinge_Panel: Tent,
  Tensor_Rod: Cylinder,
  Base_Connector: Layers,
}

export type PartsBomProps = {
  intent: DesignIntent | null
  materialName: string
  totalMassKg: number | null
}

export function PartsBom({ intent, materialName, totalMassKg }: PartsBomProps) {
  const t = useTranslations('design.parts')
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<string | null>(null)

  const parts = useMemo<PartSummary[]>(() => derivePartsFromIntent(intent), [intent])
  const withMass = useMemo(
    () => (totalMassKg != null ? apportionMass(parts, totalMassKg) : parts.map((p) => ({ ...p, mass_kg: 0 }))),
    [parts, totalMassKg],
  )
  const partCount = parts.length

  if (!intent || parts.length === 0) {
    return (
      <aside
        aria-label={t('aria_label')}
        className="flex h-full flex-col border-l border-border bg-background p-4"
      >
        <h2 className="font-display text-base font-bold tracking-tight">{t('title')}</h2>
        <p className="mt-3 text-xs text-muted-foreground">{t('empty')}</p>
      </aside>
    )
  }

  return (
    <aside
      aria-label={t('aria_label')}
      className="flex h-full flex-col border-l border-border bg-background"
    >
      <header className="border-b border-border p-4">
        <h2 className="font-display text-base font-bold tracking-tight">{t('title')}</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          {t('count', { count: partCount })}
          {totalMassKg != null && ` · ${totalMassKg.toFixed(1)} kg ${t('total')}`}
        </p>
      </header>
      <ol className="flex-1 overflow-y-auto p-2">
        {withMass.map((part) => {
          const Icon = PART_ICON[part.name] ?? Layers
          const isHidden = hidden.has(part.name)
          const isSelected = selected === part.name
          return (
            <li key={part.name}>
              <button
                type="button"
                onClick={() => setSelected(isSelected ? null : part.name)}
                aria-pressed={isSelected}
                className={cn(
                  'mb-1 flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors motion-reduce:transition-none',
                  isSelected
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-background hover:border-primary/50 hover:bg-muted/40',
                  isHidden && 'opacity-60',
                )}
              >
                <Icon
                  className={cn(
                    'mt-0.5 h-5 w-5 shrink-0',
                    part.role === 'main' ? 'text-primary' : 'text-muted-foreground',
                  )}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold">{part.name.replaceAll('_', ' ')}</p>
                    {part.role === 'main' && (
                      <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                        {t('main')}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{formatDimensions(part)}</p>
                  {part.mass_kg > 0 && (
                    <p className="mt-1 text-xs font-medium tabular-nums">{part.mass_kg.toFixed(1)} kg</p>
                  )}
                </div>
                <span
                  role="checkbox"
                  aria-checked={!isHidden}
                  aria-label={isHidden ? t('show') : t('hide')}
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation()
                    setHidden((prev) => {
                      const next = new Set(prev)
                      if (next.has(part.name)) next.delete(part.name)
                      else next.add(part.name)
                      return next
                    })
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      e.stopPropagation()
                      setHidden((prev) => {
                        const next = new Set(prev)
                        if (next.has(part.name)) next.delete(part.name)
                        else next.add(part.name)
                        return next
                      })
                    }
                  }}
                  className="mt-0.5 inline-flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {isHidden ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
      <footer className="border-t border-border p-4 text-xs text-muted-foreground">
        <p>
          <span className="font-medium text-foreground">{t('material')}:</span>{' '}
          {materialName.replaceAll('_', ' ')}
        </p>
      </footer>
    </aside>
  )
}
