'use client'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'

export function GenerateButton({
  disabled,
  onClick,
}: {
  disabled: boolean
  onClick: () => void
}) {
  const t = useTranslations('form')
  return (
    <Button onClick={onClick} disabled={disabled} size="lg" className="mt-4 w-full">
      {t('generate')}
    </Button>
  )
}
