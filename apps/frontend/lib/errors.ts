type Severity = 'error' | 'warning' | 'info'
type Action =
  | 'retry' | 'retry_later' | 'retry_after' | 'fix_field'
  | 'new_session' | 'report_bug' | 'simplify_params'
  | 'select_valid' | 'contact_support'

export type ErrorDisplay = {
  severity: Severity
  i18nKey: string
  action: Action
}

export const ERROR_MAP: Record<string, ErrorDisplay> = {
  // S1
  invalid_json_retry_failed: { severity: 'error', i18nKey: 'errors.interpret.invalid_json', action: 'retry' },
  unknown_primitive: { severity: 'error', i18nKey: 'errors.interpret.unknown_primitive', action: 'retry' },
  physical_range_violation: { severity: 'warning', i18nKey: 'errors.validation.out_of_range', action: 'fix_field' },
  vertex_ai_timeout: { severity: 'error', i18nKey: 'errors.infra.timeout', action: 'retry_later' },
  vertex_ai_rate_limit: { severity: 'warning', i18nKey: 'errors.infra.rate_limit', action: 'retry_after' },
  session_not_found: { severity: 'info', i18nKey: 'errors.session.expired', action: 'new_session' },
  session_expired: { severity: 'info', i18nKey: 'errors.session.expired', action: 'new_session' },
  ambiguous_intent: { severity: 'error', i18nKey: 'errors.interpret.invalid_json', action: 'retry' },
  unit_parse_failed: { severity: 'warning', i18nKey: 'errors.validation.out_of_range', action: 'fix_field' },
  // S2
  parameter_out_of_range: { severity: 'warning', i18nKey: 'errors.geometry.param_range', action: 'fix_field' },
  composition_rule_missing: { severity: 'error', i18nKey: 'errors.geometry.composition_missing', action: 'report_bug' },
  material_not_found: { severity: 'error', i18nKey: 'errors.geometry.unknown_material', action: 'select_valid' },
  build123d_failed: { severity: 'error', i18nKey: 'errors.geometry.build_failed', action: 'simplify_params' },
  boolean_operation_failed: { severity: 'error', i18nKey: 'errors.geometry.boolean_failed', action: 'simplify_params' },
  tessellation_failed: { severity: 'error', i18nKey: 'errors.geometry.build_failed', action: 'simplify_params' },
  step_export_failed: { severity: 'error', i18nKey: 'errors.geometry.upload_failed', action: 'retry_later' },
  glb_export_failed: { severity: 'error', i18nKey: 'errors.geometry.upload_failed', action: 'retry_later' },
  svg_export_failed: { severity: 'error', i18nKey: 'errors.geometry.upload_failed', action: 'retry_later' },
  gcs_upload_failed: { severity: 'error', i18nKey: 'errors.geometry.upload_failed', action: 'retry_later' },
  gcs_unavailable: { severity: 'warning', i18nKey: 'errors.geometry.gcs_down', action: 'retry_after' },
  cache_read_failed: { severity: 'info', i18nKey: 'errors.generic', action: 'retry' },
  // Synthetic
  connection_lost: { severity: 'error', i18nKey: 'errors.connection_lost', action: 'retry' },
  internal_error: { severity: 'error', i18nKey: 'errors.generic', action: 'contact_support' },
}

export function getErrorDisplay(code: string): ErrorDisplay {
  return ERROR_MAP[code] ?? ERROR_MAP.internal_error
}
