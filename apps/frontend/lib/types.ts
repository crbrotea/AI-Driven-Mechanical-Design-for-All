// Mirrors backend Pydantic models. Keep in sync manually for hackathon;
// generate from packages/contracts/ post-hackathon.

export type FieldSource = 'extracted' | 'defaulted' | 'missing' | 'user' | 'invalid'

export type TriStateField = {
  value: string | number | boolean | null
  source: FieldSource
  reason?: string | null
  required?: boolean
  original?: string | null
}

export type DesignIntent = {
  type: string
  fields: Record<string, TriStateField>
  composed_of: string[]
}

export type MassProperties = {
  volume_m3: number
  mass_kg: number
  center_of_mass: [number, number, number]
  bbox_m: [number, number, number, number, number, number]
}

export type GenerateArtifactUrls = {
  step_url: string
  glb_url: string
  svg_url: string
}

export type GenerateResponse = {
  cache_hit: boolean
  intent_hash: string
  artifacts: GenerateArtifactUrls
  mass_properties: MassProperties
  material_name: string
  material_density_kg_m3: number
}

export type SessionMessage = {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: unknown
  timestamp: string
}

export type Session = {
  session_id: string
  user_id: string
  language: 'es' | 'en'
  created_at: string
  updated_at: string
  messages: SessionMessage[]
  current_intent: DesignIntent | null
  user_overrides: Record<string, TriStateField>
}

export type BackendError = {
  code: string
  message: string
  field?: string | null
  primitive?: string | null
  stage?: string | null
  details?: Record<string, unknown> | null
  retry_after?: number | null
}

export type SSEEvent =
  | { event: 'thinking'; data: { message: string } }
  | { event: 'tool_call'; data: { tool: string; args?: Record<string, unknown>; reason?: string } }
  | { event: 'partial_intent'; data: Partial<DesignIntent> }
  | { event: 'progress'; data: { step: string; pct: number; primitive?: string; message?: string } }
  | { event: 'final'; data: GenerateResponse | { session_id: string; intent: DesignIntent; language: 'es' | 'en' } }
  | { event: 'error'; data: BackendError }
