'use client'
import { useState, FormEvent } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function ChatInput({
  onSubmit,
  disabled,
  initialValue = '',
}: {
  onSubmit: (value: string) => void
  disabled: boolean
  initialValue?: string
}) {
  const t = useTranslations('chat')
  const [value, setValue] = useState(initialValue)

  function handle(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <form onSubmit={handle} className="flex gap-2 border-t border-border p-3">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t('placeholder')}
        disabled={disabled}
        aria-label={t('placeholder')}
      />
      <Button type="submit" disabled={disabled || !value.trim()}>
        {t('send')}
      </Button>
    </form>
  )
}
