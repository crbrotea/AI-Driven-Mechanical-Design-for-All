import { useTranslations } from 'next-intl'
import type { SSEEvent } from '@/lib/types'

export function StreamingIndicator({ events }: { events: SSEEvent[] }) {
  const t = useTranslations('chat')
  const toolCalls = events.filter((e) => e.event === 'tool_call')

  return (
    <div className="flex flex-col gap-1 italic text-muted-foreground">
      <div>{t('thinking')}</div>
      {toolCalls.map((e, i) => {
        const tool = (e.data as { tool: string }).tool
        const args = (e.data as { args?: Record<string, unknown> }).args ?? {}
        const labelKey = `tool_calls.${tool}` as const
        return (
          <div key={i} className="text-xs">
            🔍 {t(labelKey, { primitive: args.name as string, material: args.name as string })}
          </div>
        )
      })}
    </div>
  )
}
