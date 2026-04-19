import type { PropsWithChildren } from 'react'

export function Tooltip({ content, children }: PropsWithChildren<{ content: string }>) {
  return <span title={content}>{children}</span>
}
