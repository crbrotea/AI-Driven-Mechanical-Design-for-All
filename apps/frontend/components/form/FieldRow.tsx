'use client'
import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import type { TriStateField } from '@/lib/types'

const BORDER_BY_SOURCE: Record<TriStateField['source'], string> = {
  extracted: 'border-green-500',
  defaulted: 'border-blue-500',
  missing: 'border-red-500',
  user: 'border-purple-500',
  invalid: 'border-yellow-500',
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
            'rounded px-2 py-0.5 text-[10px]',
            field.source === 'extracted' && 'bg-green-100 text-green-700',
            field.source === 'defaulted' && 'bg-blue-100 text-blue-700',
            field.source === 'missing' && 'bg-red-100 text-red-700',
            field.source === 'user' && 'bg-purple-100 text-purple-700',
            field.source === 'invalid' && 'bg-yellow-100 text-yellow-700',
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
      />
    </div>
  )
}
