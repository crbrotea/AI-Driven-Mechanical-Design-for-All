import { cn } from '@/lib/utils'

export type ChatRole = 'user' | 'assistant' | 'tool_call'

export function ChatMessage({
  role,
  content,
  toolLabel,
}: {
  role: ChatRole
  content: string
  toolLabel?: string
}) {
  if (role === 'tool_call') {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground italic">
        <span>🔧</span>
        <span>{toolLabel ?? content}</span>
      </div>
    )
  }
  return (
    <div
      className={cn(
        'rounded-lg px-3 py-2 text-sm max-w-[85%]',
        role === 'user' ? 'ml-auto bg-primary text-primary-foreground' : 'bg-muted',
      )}
    >
      {content}
    </div>
  )
}
