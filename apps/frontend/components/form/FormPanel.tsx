'use client'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useIntent } from '@/lib/hooks/useIntent'
import { FieldRow } from './FieldRow'
import { MaterialSelector } from './MaterialSelector'
import { GenerateButton } from './GenerateButton'
import type { DesignIntent, TriStateField } from '@/lib/types'

export function FormPanel({
  sessionId,
  overrideIntent,
  onGenerate,
}: {
  sessionId: string | null
  overrideIntent?: DesignIntent | null
  onGenerate: (intent: DesignIntent, material: string) => void
}) {
  const t = useTranslations('form')
  const { intent: fetchedIntent, hasMissingFields: sessionHasMissing, refineIntent } = useIntent(sessionId)
  const intent = overrideIntent ?? fetchedIntent
  const [material, setMaterial] = useState('steel_a36')
  // Track which previously-missing fields have been given a value by the user
  const [filledMissing, setFilledMissing] = useState<Set<string>>(new Set())

  if (!intent) {
    return <div className="p-4 text-muted-foreground text-sm">{t('placeholder')}</div>
  }

  // When overrideIntent is active we compute hasMissingFields locally, accounting for
  // fields the user has already typed a value into (which refine has not yet persisted).
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

  return (
    <section className="flex h-full flex-col border-r border-border p-4">
      <h2 className="text-lg font-semibold">{t('title')}</h2>
      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
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
      <GenerateButton
        disabled={hasMissingFields}
        onClick={() => onGenerate(intent, material)}
      />
    </section>
  )
}
