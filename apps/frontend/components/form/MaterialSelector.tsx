'use client'
import { useTranslations } from 'next-intl'

const MATERIALS = [
  { id: 'steel_a36', label: 'Steel A36' },
  { id: 'aluminum_6061', label: 'Aluminum 6061-T6' },
  { id: 'stainless_304', label: 'Stainless 304' },
  { id: 'titanium_grade2', label: 'Titanium Grade 2' },
  { id: 'abs', label: 'ABS Plastic' },
  { id: 'pla_biodegradable', label: 'PLA (biodegradable)' },
  { id: 'bamboo_laminated', label: 'Laminated Bamboo' },
]

export function MaterialSelector({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const t = useTranslations('form')
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium">{t('material')}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-md border border-border bg-background px-3 text-sm"
      >
        {MATERIALS.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
          </option>
        ))}
      </select>
    </label>
  )
}
