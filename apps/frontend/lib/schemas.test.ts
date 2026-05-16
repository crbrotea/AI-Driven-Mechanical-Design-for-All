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

import {
  analysisResultSchema,
  naturalReportSchema,
  deliverablesSchema,
} from './schemas'

describe('analysisResultSchema', () => {
  it('accepts a valid result', () => {
    const ok = analysisResultSchema.parse({
      intent_type: 'Flywheel_Rim',
      material_name: 'steel_a36',
      material_yield_mpa: 250,
      formula: 'sigma = rho*omega^2*R^2',
      stress_max_pa: 1.93e8,
      displacement_max_m: 4.84e-4,
      safety_factor: 1.29,
      verdict: 'warn',
      inputs: { angular_velocity_rad_s: 314.16 },
      notes: null,
    })
    expect(ok.verdict).toBe('warn')
  })

  it('rejects an unknown verdict', () => {
    expect(() =>
      analysisResultSchema.parse({
        intent_type: 'Flywheel_Rim', material_name: 'steel_a36',
        material_yield_mpa: 250, formula: 'x',
        stress_max_pa: 0, displacement_max_m: 0,
        safety_factor: 0, verdict: 'oops', inputs: {},
      }),
    ).toThrow()
  })
})

describe('naturalReportSchema', () => {
  it('defaults missing lists to empty', () => {
    const r = naturalReportSchema.parse({ summary: 'ok' })
    expect(r.risks).toEqual([])
    expect(r.suggestions).toEqual([])
    expect(r.analogies).toEqual([])
    expect(r.facts_used).toEqual([])
  })
})

describe('deliverablesSchema', () => {
  it('requires the five URLs and cache fields', () => {
    const d = deliverablesSchema.parse({
      report_pdf_url: 'a', drawing_pdf_url: 'b',
      step_url: 'c', glb_url: 'd', svg_url: 'e',
      cache_hit: true, cache_key: 'abc',
    })
    expect(d.cache_hit).toBe(true)
  })
})
