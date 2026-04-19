import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextIntlClientProvider } from 'next-intl'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { FormPanel } from '@/components/form/FormPanel'
import enMessages from '@/messages/en.json'
import type { DesignIntent } from '@/lib/types'
import { useState } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'

function AppStub() {
  const [intent, setIntent] = useState<DesignIntent | null>(null)
  const [generated, setGenerated] = useState(false)
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <ChatPanel sessionId="test-sid" onIntentReady={(i) => setIntent(i as DesignIntent)} />
      <FormPanel
        sessionId="test-sid"
        overrideIntent={intent}
        onGenerate={() => setGenerated(true)}
      />
      {generated && <div data-testid="generated-marker">generated</div>}
    </NextIntlClientProvider>
  )
}

describe('happy path (mocked)', () => {
  beforeEach(() => {
    localStorage.clear()
    useUIStore.setState({ locale: 'en' })
  })

  it('chat → form → generate produces the marker', async () => {
    const user = userEvent.setup()
    render(<AppStub />)

    // Chat phase
    const input = await screen.findByPlaceholderText(/describe your design/i)
    await user.type(input, 'design a flywheel')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for form to render with fields
    await waitFor(() => expect(screen.getByText(/design parameters/i)).toBeInTheDocument(), {
      timeout: 5000,
    })
    expect(screen.getByLabelText('outer_diameter_m')).toBeInTheDocument()
    expect(screen.getByText('Required')).toBeInTheDocument() // missing thickness_m

    // Fill missing field + click generate
    await user.type(screen.getByLabelText('thickness_m'), '0.05')
    await waitFor(() => expect(screen.getByRole('button', { name: /generate/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByTestId('generated-marker')).toBeInTheDocument())
  })
})
