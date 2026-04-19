import { describe, it, expect } from 'vitest'
import { getErrorDisplay, ERROR_MAP } from './errors'

const BACKEND_CODES = [
  'invalid_json_retry_failed', 'unknown_primitive', 'physical_range_violation',
  'vertex_ai_timeout', 'vertex_ai_rate_limit', 'session_not_found', 'session_expired',
  'ambiguous_intent', 'unit_parse_failed',
  'parameter_out_of_range', 'composition_rule_missing', 'material_not_found',
  'build123d_failed', 'boolean_operation_failed', 'tessellation_failed',
  'step_export_failed', 'glb_export_failed', 'svg_export_failed',
  'gcs_upload_failed', 'gcs_unavailable', 'cache_read_failed',
  'connection_lost', 'internal_error',
]

describe('ERROR_MAP', () => {
  it('maps every backend code', () => {
    for (const code of BACKEND_CODES) {
      expect(ERROR_MAP[code]).toBeDefined()
    }
  })

  it('unknown code falls back to internal_error', () => {
    expect(getErrorDisplay('nonexistent').i18nKey).toBe('errors.generic')
  })
})
