// components/viewer/MassPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { MassPanel } from './MassPanel'
import enMessages from '@/messages/en.json'

describe('MassPanel', () => {
  it('renders mass, volume, and bbox', () => {
    render(
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <MassPanel
          properties={{
            mass_kg: 74.0,
            volume_m3: 0.00942,
            center_of_mass: [0, 0, 0.025],
            bbox_m: [0, 0, 0, 0.5, 0.5, 0.05],
          }}
        />
      </NextIntlClientProvider>,
    )
    expect(screen.getByText(/74\.0 kg/)).toBeInTheDocument()
    expect(screen.getByText(/0\.0094/)).toBeInTheDocument()
    expect(screen.getByText(/0\.500 × 0\.500 × 0\.050/)).toBeInTheDocument()
  })
})
