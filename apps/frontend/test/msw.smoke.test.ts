import { describe, it, expect } from 'vitest'
import { apiPost } from '@/lib/api-client'

describe('MSW smoke', () => {
  it('intercepts /interpret/refine', async () => {
    // apiPost returns JSON; we hit the refine endpoint
    const res = await apiPost<{ intent: { type: string } }>('/interpret/refine', {
      session_id: 'x',
      field_updates: {},
    })
    expect(res.intent.type).toBe('Flywheel_Rim')
  })
})
