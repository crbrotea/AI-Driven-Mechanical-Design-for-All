// components/form/FieldRow.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextIntlClientProvider } from 'next-intl'
import { FieldRow } from './FieldRow'
import enMessages from '@/messages/en.json'

function Wrap(children: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      {children}
    </NextIntlClientProvider>
  )
}

describe('FieldRow', () => {
  it('renders extracted badge', () => {
    render(
      Wrap(
        <FieldRow name="d" field={{ value: 0.05, source: 'extracted' }} onChange={() => {}} />,
      ),
    )
    expect(screen.getByText('From your input')).toBeInTheDocument()
  })

  it('renders missing as Required', () => {
    render(
      Wrap(
        <FieldRow
          name="d"
          field={{ value: null, source: 'missing', required: true }}
          onChange={() => {}}
        />,
      ),
    )
    expect(screen.getByText('Required')).toBeInTheDocument()
  })

  it('fires onChange when typing', async () => {
    let captured = ''
    render(
      Wrap(
        <FieldRow name="d" field={{ value: 0.1, source: 'defaulted', reason: 'x' }} onChange={(v) => (captured = v)} />,
      ),
    )
    await userEvent.clear(screen.getByLabelText('d'))
    await userEvent.type(screen.getByLabelText('d'), '0.2')
    expect(captured).toBe('0.2')
  })
})
