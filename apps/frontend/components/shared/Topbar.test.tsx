// components/shared/Topbar.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ClientProviders } from './ClientProviders'
import { Topbar } from './Topbar'
import { useUIStore } from '@/lib/stores/uiStore'

function TopbarWithProviders() {
  return (
    <ClientProviders>
      <Topbar />
    </ClientProviders>
  )
}

describe('Topbar', () => {
  beforeEach(() => {
    localStorage.clear()
    useUIStore.setState({ locale: 'en', theme: 'light' })
  })

  it('renders locale toggle and shows current opposite', async () => {
    render(<TopbarWithProviders />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Switch to ES/i })).toBeInTheDocument()
    )
  })

  it('clicking locale button flips state', async () => {
    const user = userEvent.setup()
    render(<TopbarWithProviders />)
    await waitFor(() => screen.getByRole('button', { name: /Switch to ES/i }))
    await user.click(screen.getByRole('button', { name: /Switch to ES/i }))
    expect(useUIStore.getState().locale).toBe('es')
  })

  it('clicking theme button toggles theme', async () => {
    const user = userEvent.setup()
    render(<TopbarWithProviders />)
    await waitFor(() => screen.getByRole('button', { name: /Toggle theme/i }))
    await user.click(screen.getByRole('button', { name: /Toggle theme/i }))
    expect(useUIStore.getState().theme).toBe('dark')
  })

  it('locale toggle actually changes translations', async () => {
    const user = userEvent.setup()
    render(<TopbarWithProviders />)
    // English initial: button label is "Switch to ES"
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Switch to ES/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /Switch to ES/i }))
    // After toggle, locale is 'es'. Spanish messages load → aria-label becomes "Cambiar a EN"
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Cambiar a EN/i })).toBeInTheDocument()
    )
  })
})
