'use client'
import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { useIntent } from '@/lib/hooks/useIntent'
import { FieldRow } from './FieldRow'
import { MaterialSelector } from './MaterialSelector'
import { GenerateButton } from './GenerateButton'
import { derivePartsFromIntent, formatDimensions } from '@/lib/parts'
import type { DesignIntent, TriStateField } from '@/lib/types'

export function FormPanel({
  sessionId,
  overrideIntent,
  onGenerate,
  onMaterialChange,
}: {
  sessionId: string | null
  overrideIntent?: DesignIntent | null
  onGenerate: (intent: DesignIntent, material: string) => void
  onMaterialChange?: (material: string) => void
}) {
  const t = useTranslations('form')
  const { intent: fetchedIntent, hasMissingFields: sessionHasMissing, refineIntent } = useIntent(sessionId)
  const intent = overrideIntent ?? fetchedIntent
  const [material, setMaterial] = useState('steel_a36')
  const [filledMissing, setFilledMissing] = useState<Set<string>>(new Set())

  useEffect(() => {
    onMaterialChange?.(material)
  }, [material, onMaterialChange])

  if (!intent) {
    return <div className="p-4 text-muted-foreground text-sm">{t('placeholder')}</div>
  }

  const hasMissingFields = overrideIntent
    ? Object.entries(intent.fields).some(
        ([name, f]) =>
          (f as TriStateField).source === 'missing' && !filledMissing.has(name),
      )
    : sessionHasMissing

  async function onFieldChange(name: string, value: string) {
    const num = value === '' ? null : Number.isFinite(Number(value)) ? Number(value) : value
    if (num !== null && num !== '') {
      setFilledMissing((prev) => new Set([...prev, name]))
    } else {
      setFilledMissing((prev) => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
    }
    await refineIntent({ [name]: num })
  }

  const allParts = derivePartsFromIntent(intent)
  const composedParts = allParts.filter((p) => p.role === 'composed')

  return (
    <section className="flex h-full flex-col">
      <header className="border-b border-border p-4">
        <h2 className="font-display text-lg font-bold tracking-tight">{t('title')}</h2>
        <p className="mt-1 text-xs text-muted-foreground">{intent.type.replaceAll('_', ' ')}</p>
      </header>
      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm">{t('section_main')}</h3>
            <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
              {t('main_badge')}
            </span>
          </div>
          {Object.entries(intent.fields).map(([name, field]) => (
            <FieldRow
              key={name}
              name={name}
              field={field}
              onChange={(v) => onFieldChange(name, v)}
            />
          ))}
          <MaterialSelector value={material} onChange={setMaterial} />
        </div>

        {composedParts.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-sm">{t('section_derived')}</h3>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {t('derived_badge')}
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">{t('derived_hint')}</p>
            {composedParts.map((part) => (
              <div key={part.name} className="rounded-md border border-border bg-muted/30 p-3">
                <p className="text-sm font-semibold">{part.name.replaceAll('_', ' ')}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">{formatDimensions(part)}</p>
                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                  {Object.entries(part.fields).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-1">
                      <dt className="text-muted-foreground truncate">{k}</dt>
                      <dd className="font-mono tabular-nums">{v.toFixed(3)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="border-t border-border p-4">
        <GenerateButton
          disabled={hasMissingFields}
          onClick={() => onGenerate(intent, material)}
        />
      </div>
    </section>
  )
}
