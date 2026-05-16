import type { SSEEvent } from '@/lib/types'

export function ProgressStream({ events }: { events: SSEEvent[] }) {
  const progressEvents = events.filter((e) => e.event === 'progress')
  const last = progressEvents.at(-1)
  if (!last) return null
  const data = last.data as { step: string; pct: number; primitive?: string }
  return (
    <div
      className="flex w-full max-w-xs flex-col items-center gap-2 text-sm"
      role="status"
      aria-live="polite"
    >
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={data.pct}
        aria-label={`Generation progress: ${data.step}`}
      >
        <div
          className="h-full bg-primary transition-all motion-reduce:transition-none"
          style={{ width: `${data.pct}%` }}
        />
      </div>
      <div className="text-muted-foreground">
        {data.step} {data.primitive && `— ${data.primitive}`} ({data.pct}%)
      </div>
    </div>
  )
}
