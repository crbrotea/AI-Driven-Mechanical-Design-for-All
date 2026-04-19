'use client'
import { Button } from '@/components/ui/button'

export default function DesignError({
  error,
  reset,
}: {
  error: Error
  reset: () => void
}) {
  return (
    <div className="grid h-screen place-items-center">
      <div className="max-w-md text-center">
        <h2 className="text-2xl font-bold">Something broke</h2>
        <p className="my-4 text-sm text-muted-foreground">{error.message}</p>
        <Button onClick={reset}>Reload</Button>
      </div>
    </div>
  )
}
