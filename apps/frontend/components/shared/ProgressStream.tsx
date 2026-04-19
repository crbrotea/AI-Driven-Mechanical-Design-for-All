import type { SSEEvent } from '@/lib/types'

export function ProgressStream({ events }: { events: SSEEvent[] }) {
  const progressEvents = events.filter((e) => e.event === 'progress')
  const last = progressEvents.at(-1)
  if (!last) return null
  const data = last.data as { step: string; pct: number; primitive?: string }
  return (
    <div className="flex flex-col items-center gap-2 text-sm">
      <div className="h-2 w-64 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${data.pct}%` }} />
      </div>
      <div className="text-muted-foreground">
        {data.step} {data.primitive && `— ${data.primitive}`} ({data.pct}%)
      </div>
    </div>
  )
}
