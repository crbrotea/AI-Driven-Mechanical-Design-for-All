// components/shared/Topbar.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextIntlClientProvider } from 'next-intl'
import { Topbar } from './Topbar'
import { useUIStore } from '@/lib/stores/uiStore'
import enMessages from '@/messages/en.json'

function TopbarWithProviders() {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <Topbar />
    </NextIntlClientProvider>
  )
}

describe('Topbar', () => {
  beforeEach(() => {
    localStorage.clear()
    useUIStore.setState({ locale: 'en', theme: 'light' })
  })

  it('renders locale toggle and shows current opposite', () => {
    render(<TopbarWithProviders />)
    expect(screen.getByRole('button', { name: /Switch to ES/i })).toBeInTheDocument()
  })

  it('clicking locale button flips state', async () => {
    const user = userEvent.setup()
    render(<TopbarWithProviders />)
    await user.click(screen.getByRole('button', { name: /Switch to ES/i }))
    expect(useUIStore.getState().locale).toBe('es')
  })

  it('clicking theme button toggles theme', async () => {
    const user = userEvent.setup()
    render(<TopbarWithProviders />)
    await user.click(screen.getByRole('button', { name: /Toggle theme/i }))
    expect(useUIStore.getState().theme).toBe('dark')
  })
})
