// components/shared/ErrorBanner.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextIntlClientProvider } from 'next-intl'
import { ErrorBanner } from './ErrorBanner'
import enMessages from '@/messages/en.json'

describe('ErrorBanner', () => {
  it('renders error message and retry action for known code', async () => {
    let retried = false
    render(
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <ErrorBanner
          error={{ code: 'vertex_ai_timeout', message: 'timeout' }}
          onRetry={() => {
            retried = true
          }}
        />
      </NextIntlClientProvider>,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button'))
    expect(retried).toBe(true)
  })

  it('falls back to generic for unknown code', () => {
    render(
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <ErrorBanner error={{ code: 'nonexistent_code', message: 'x' }} />
      </NextIntlClientProvider>,
    )
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
  })
})
