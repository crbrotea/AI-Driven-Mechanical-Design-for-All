import { z } from 'zod'

export const TriStateFieldSchema = z.object({
  value: z.union([z.string(), z.number(), z.boolean(), z.null()]),
  source: z.enum(['extracted', 'defaulted', 'missing', 'user', 'invalid']),
  reason: z.string().nullable().optional(),
  required: z.boolean().optional(),
  original: z.string().nullable().optional(),
})

export const DesignIntentSchema = z.object({
  type: z.string(),
  fields: z.record(TriStateFieldSchema),
  composed_of: z.array(z.string()),
})

export const MassPropertiesSchema = z.object({
  volume_m3: z.number(),
  mass_kg: z.number(),
  center_of_mass: z.tuple([z.number(), z.number(), z.number()]),
  bbox_m: z.tuple([z.number(), z.number(), z.number(), z.number(), z.number(), z.number()]),
})

export const GenerateArtifactUrlsSchema = z.object({
  step_url: z.string(),
  glb_url: z.string(),
  svg_url: z.string(),
})

export const GenerateResponseSchema = z.object({
  cache_hit: z.boolean(),
  intent_hash: z.string(),
  artifacts: GenerateArtifactUrlsSchema,
  mass_properties: MassPropertiesSchema,
  material_name: z.string(),
  material_density_kg_m3: z.number(),
})

export const BackendErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  field: z.string().nullable().optional(),
  primitive: z.string().nullable().optional(),
  stage: z.string().nullable().optional(),
  details: z.record(z.unknown()).nullable().optional(),
  retry_after: z.number().nullable().optional(),
})

export const SessionMessageSchema = z.object({
  role: z.enum(['user', 'assistant', 'tool']),
  content: z.string(),
  tool_calls: z.unknown().optional(),
  timestamp: z.string(),
})

export const SessionSchema = z.object({
  session_id: z.string(),
  user_id: z.string(),
  language: z.enum(['es', 'en']),
  created_at: z.string(),
  updated_at: z.string(),
  messages: z.array(SessionMessageSchema),
  current_intent: DesignIntentSchema.nullable(),
  user_overrides: z.record(TriStateFieldSchema),
})
