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
  const variant =
    display.severity === 'error'
      ? 'bg-danger text-danger-foreground'
      : display.severity === 'warning'
        ? 'bg-warning text-warning-foreground'
        : 'bg-info text-info-foreground'
  return (
    <div className={`flex items-center justify-between rounded-md p-3 ${variant}`} role="alert">
      <span>
        {t(display.i18nKey, { field: error.field, seconds: error.retry_after })}
      </span>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {t(`actions.${display.action}`)}
        </Button>
      )}
    </div>
  )
}
