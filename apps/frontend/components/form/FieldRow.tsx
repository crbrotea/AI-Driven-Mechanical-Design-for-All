'use client'
import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import type { TriStateField } from '@/lib/types'

const BORDER_BY_SOURCE: Record<TriStateField['source'], string> = {
  extracted: 'border-success',
  defaulted: 'border-info',
  missing: 'border-danger',
  user: 'border-primary',
  invalid: 'border-warning',
}

export function FieldRow({
  name,
  field,
  onChange,
}: {
  name: string
  field: TriStateField
  onChange: (value: string) => void
}) {
  const t = useTranslations('form')
  const [localValue, setLocalValue] = useState(field.value === null ? '' : String(field.value))

  useEffect(() => {
    setLocalValue(field.value === null ? '' : String(field.value))
  }, [field.value])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setLocalValue(e.target.value)
    onChange(e.target.value)
  }

  return (
    <div className="flex flex-col gap-1">
      <label className="flex items-center justify-between text-xs">
        <span className="font-medium">{name}</span>
        <span
          className={cn(
            'rounded px-2 py-0.5 text-[10px] font-medium',
            field.source === 'extracted' && 'bg-success/15 text-success',
            field.source === 'defaulted' && 'bg-info/15 text-info',
            field.source === 'missing' && 'bg-danger/15 text-danger',
            field.source === 'user' && 'bg-primary/15 text-primary',
            field.source === 'invalid' && 'bg-warning/15 text-warning',
          )}
          title={field.reason ?? undefined}
        >
          {t(`source.${field.source}`)}
        </span>
      </label>
      <Input
        type="text"
        value={localValue}
        onChange={handleChange}
        className={cn(BORDER_BY_SOURCE[field.source])}
        aria-label={name}
        aria-required={field.required}
        aria-invalid={field.source === 'missing' || field.source === 'invalid'}
      />
    </div>
  )
}
