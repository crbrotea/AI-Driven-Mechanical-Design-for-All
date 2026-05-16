'use client'
import { useEffect, useState } from 'react'

type Toast = { id: number; message: string; severity: 'info' | 'warning' | 'error' }

let push: ((t: Omit<Toast, 'id'>) => void) | null = null
let id = 0

export function toast(message: string, severity: Toast['severity'] = 'info') {
  push?.({ message, severity })
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([])
  useEffect(() => {
    push = (t) => {
      const nextId = ++id
      setToasts((prev) => [...prev, { ...t, id: nextId }])
      setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== nextId)), 4000)
    }
    return () => {
      push = null
    }
  }, [])
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite" aria-atomic="true">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={
            'rounded-md px-4 py-2 text-sm shadow-lg ' +
            (t.severity === 'error'
              ? 'bg-danger text-danger-foreground'
              : t.severity === 'warning'
                ? 'bg-warning text-warning-foreground'
                : 'bg-info text-info-foreground')
          }
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
