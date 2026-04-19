import { describe, it, expect } from 'vitest'
import { DesignIntentSchema, GenerateResponseSchema, BackendErrorSchema } from './schemas'

describe('schemas', () => {
  it('validates a complete DesignIntent', () => {
    const intent = {
      type: 'Flywheel_Rim',
      fields: {
        outer_diameter_m: { value: 0.5, source: 'extracted' },
        inner_diameter_m: { value: null, source: 'missing', required: true },
      },
      composed_of: ['Shaft'],
    }
    expect(DesignIntentSchema.parse(intent)).toMatchObject(intent)
  })

  it('rejects invalid source', () => {
    expect(() =>
      DesignIntentSchema.parse({
        type: 'Shaft',
        fields: { d: { value: 0.05, source: 'weird' } },
        composed_of: [],
      }),
    ).toThrow()
  })

  it('validates a GenerateResponse', () => {
    const res = {
      cache_hit: false,
      intent_hash: 'abc123',
      artifacts: {
        step_url: 'https://example.com/s',
        glb_url: 'https://example.com/g',
        svg_url: 'https://example.com/v',
      },
      mass_properties: {
        volume_m3: 0.01,
        mass_kg: 78.5,
        center_of_mass: [0, 0, 0.025],
        bbox_m: [0, 0, 0, 0.5, 0.5, 0.05],
      },
      material_name: 'steel_a36',
      material_density_kg_m3: 7850,
    }
    expect(GenerateResponseSchema.parse(res)).toMatchObject(res)
  })

  it('validates a BackendError', () => {
    const err = { code: 'invalid_json_retry_failed', message: 'failed' }
    expect(BackendErrorSchema.parse(err).code).toBe('invalid_json_retry_failed')
  })
})
