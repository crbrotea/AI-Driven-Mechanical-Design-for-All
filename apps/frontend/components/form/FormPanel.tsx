'use client'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useIntent } from '@/lib/hooks/useIntent'
import { FieldRow } from './FieldRow'
import { MaterialSelector } from './MaterialSelector'
import { GenerateButton } from './GenerateButton'
import type { DesignIntent } from '@/lib/types'

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
  const { intent: fetchedIntent, hasMissingFields, refineIntent } = useIntent(sessionId)
  const intent = overrideIntent ?? fetchedIntent
  const [material, setMaterial] = useState('steel_a36')

  if (!intent) {
    return <div className="p-4 text-sm text-muted-foreground">{t('placeholder')}</div>
  }

  async function onFieldChange(name: string, value: string) {
    const num = value === '' ? null : Number.isFinite(Number(value)) ? Number(value) : value
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
