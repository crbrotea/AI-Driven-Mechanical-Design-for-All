'use client'
import { useState, type ReactNode } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'

export type TabKey = 'parameters' | 'analysis' | 'narrative' | 'deliverables'

export type TabDef = {
  key: TabKey
  available: boolean
  badge?: string
}

export function PipelineTabs({
  tabs,
  defaultTab = 'parameters',
  children,
}: {
  tabs: TabDef[]
  defaultTab?: TabKey
  children: (active: TabKey) => ReactNode
}) {
  const t = useTranslations('design.tabs')
  const [active, setActive] = useState<TabKey>(defaultTab)
  return (
    <section className="flex h-full flex-col">
      <div role="tablist" aria-label={t('aria_label')} className="flex shrink-0 gap-1 border-b border-border px-2">
        {tabs.map((tab) => {
          const isActive = tab.key === active
          return (
            <button
              key={tab.key}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.key}`}
              id={`tab-${tab.key}`}
              disabled={!tab.available}
              onClick={() => setActive(tab.key)}
              className={cn(
                'relative inline-flex h-10 items-center gap-2 px-4 text-sm font-medium transition-colors motion-reduce:transition-none',
                'disabled:cursor-not-allowed disabled:text-muted-foreground/60',
                isActive
                  ? 'text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t(tab.key)}
              {tab.badge && (
                <span className="rounded bg-success/15 px-1.5 py-0.5 text-[10px] font-bold text-success">
                  {tab.badge}
                </span>
              )}
              {isActive && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-primary" aria-hidden="true" />}
            </button>
          )
        })}
      </div>
      <div
        role="tabpanel"
        id={`tabpanel-${active}`}
        aria-labelledby={`tab-${active}`}
        className="flex-1 overflow-y-auto p-4"
      >
        {children(active)}
      </div>
    </section>
  )
}
