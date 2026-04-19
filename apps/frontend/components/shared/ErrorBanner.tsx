'use client'
import { useTranslations } from 'next-intl'
import { getErrorDisplay } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import type { BackendError } from '@/lib/types'

export function ErrorBanner({
  error,
  onRetry,
}: {
  error: BackendError
  onRetry?: () => void
}) {
  const t = useTranslations()
  const display = getErrorDisplay(error.code)
  const bg =
    display.severity === 'error' ? 'bg-red-600' : display.severity === 'warning' ? 'bg-yellow-500' : 'bg-blue-600'
  return (
    <div className={`flex items-center justify-between rounded-md p-3 text-white ${bg}`} role="alert">
      <span>
        {/* @ts-expect-error dynamic key */}
        {t(display.i18nKey, { field: error.field, seconds: error.retry_after })}
      </span>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {/* @ts-expect-error dynamic key */}
          {t(`actions.${display.action}`)}
        </Button>
      )}
    </div>
  )
}
