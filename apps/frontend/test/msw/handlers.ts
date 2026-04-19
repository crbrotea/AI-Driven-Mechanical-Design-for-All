import { http, HttpResponse } from 'msw'
import type { DesignIntent, GenerateResponse } from '@/lib/types'

const FLYWHEEL_INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: {
    outer_diameter_m: { value: 0.5, source: 'extracted' },
    inner_diameter_m: { value: 0.1, source: 'defaulted', reason: 'common ratio 1:5', required: true },
    thickness_m: { value: null, source: 'missing', required: true },
    rpm: { value: 3000, source: 'extracted' },
  },
  composed_of: ['Shaft'],
}

const FLYWHEEL_GENERATE: GenerateResponse = {
  cache_hit: false,
  intent_hash: 'c03a446d17fc0fd5',
  artifacts: {
    step_url: 'https://mock/step',
    glb_url: '/mock.glb',
    svg_url: 'https://mock/svg',
  },
  mass_properties: {
    volume_m3: 0.00942,
    mass_kg: 74.0,
    center_of_mass: [0, 0, 0.025],
    bbox_m: [-0.25, -0.25, 0, 0.25, 0.25, 0.05],
  },
  material_name: 'steel_a36',
  material_density_kg_m3: 7850,
}

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('')
}

export const handlers = [
  http.post('*/interpret', async () => {
    return new HttpResponse(
      sseBody([
        { event: 'thinking', data: { message: 'Analyzing...' } },
        { event: 'tool_call', data: { tool: 'list_primitives' } },
        { event: 'tool_call', data: { tool: 'get_primitive_schema', args: { name: 'Flywheel_Rim' } } },
        { event: 'final', data: { session_id: 'test-sid', intent: FLYWHEEL_INTENT, language: 'en' } },
      ]),
      { headers: { 'Content-Type': 'text/event-stream' } },
    )
  }),

  http.post('*/interpret/refine', () => HttpResponse.json({ intent: FLYWHEEL_INTENT })),

  http.get('*/interpret/sessions/:id', ({ params }) => {
    if (params.id === 'expired') return new HttpResponse(null, { status: 404 })
    return HttpResponse.json({
      session: {
        session_id: params.id,
        user_id: 'anonymous',
        language: 'en',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
        current_intent: FLYWHEEL_INTENT,
        user_overrides: {},
      },
    })
  }),

  http.post('*/generate', () => {
    return new HttpResponse(
      sseBody([
        { event: 'progress', data: { step: 'building_main', pct: 20 } },
        { event: 'progress', data: { step: 'fusing_assembly', pct: 40 } },
        { event: 'progress', data: { step: 'exporting', pct: 70 } },
        { event: 'final', data: FLYWHEEL_GENERATE },
      ]),
      { headers: { 'Content-Type': 'text/event-stream' } },
    )
  }),

  http.get('*/generate/artifacts/:hash', ({ params }) => {
    if (params.hash === 'c03a446d17fc0fd5') return HttpResponse.json(FLYWHEEL_GENERATE)
    return new HttpResponse(null, { status: 404 })
  }),
]
