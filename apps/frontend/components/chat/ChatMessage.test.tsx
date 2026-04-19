import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatMessage } from './ChatMessage'

describe('ChatMessage', () => {
  it('renders user message with primary styling', () => {
    const { container } = render(<ChatMessage role="user" content="hello" />)
    expect(container.firstChild).toHaveClass(/bg-primary/)
  })

  it('renders tool_call label', () => {
    render(<ChatMessage role="tool_call" content="list" toolLabel="Searching" />)
    expect(screen.getByText('Searching')).toBeInTheDocument()
  })
})
