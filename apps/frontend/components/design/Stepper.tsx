'use client'
import { Check } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'

export type StepKey = 'describe' | 'configure' | 'build' | 'validate' | 'ship'

const STEPS: StepKey[] = ['describe', 'configure', 'build', 'validate', 'ship']

export type StepperState = {
  describe: boolean
  configure: boolean
  build: boolean
  validate: boolean
  ship: boolean
}

function activeStep(state: StepperState): StepKey {
  if (!state.describe) return 'describe'
  if (!state.configure) return 'configure'
  if (!state.build) return 'build'
  if (!state.validate) return 'validate'
  return 'ship'
}

export function Stepper({ state }: { state: StepperState }) {
  const t = useTranslations('design.steps')
  const current = activeStep(state)
  return (
    <nav
      aria-label={t('aria_label')}
      className="border-b border-border bg-background"
    >
      <ol className="mx-auto flex max-w-7xl items-center gap-1 px-4 py-3 md:gap-3 md:px-6">
        {STEPS.map((key, i) => {
          const done = state[key]
          const isCurrent = key === current
          const number = i + 1
          return (
            <li key={key} className="flex flex-1 items-center gap-2 min-w-0">
              <div
                className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-colors motion-reduce:transition-none',
                  done && 'border-success bg-success text-success-foreground',
                  !done && isCurrent && 'border-primary bg-primary text-primary-foreground',
                  !done && !isCurrent && 'border-border bg-background text-muted-foreground',
                )}
                aria-current={isCurrent ? 'step' : undefined}
              >
                {done ? (
                  <Check className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <span>{number}</span>
                )}
              </div>
              <div className="hidden min-w-0 md:block">
                <p
                  className={cn(
                    'truncate text-xs font-semibold',
                    isCurrent ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {t(`${key}.title`)}
                </p>
                <p className="truncate text-[11px] text-muted-foreground">{t(`${key}.subtitle`)}</p>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    'h-px flex-1 min-w-4 transition-colors motion-reduce:transition-none',
                    done ? 'bg-success' : 'bg-border',
                  )}
                  aria-hidden="true"
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
