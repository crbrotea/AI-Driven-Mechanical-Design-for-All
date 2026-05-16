/**
 * Client-side mirror of the backend geometry composition rules
 * (apps/backend/services/geometry/composition_rules.py). Lets the UI list
 * every part in an assembly with its derived dimensions and an estimated
 * mass share, without an extra backend round-trip.
 */
import type { DesignIntent } from '@/lib/types'

export type DerivedFields = Record<string, number>

export type PartSummary = {
  name: string
  role: 'main' | 'composed'
  fields: DerivedFields
  volume_m3: number
}

type CompositionRule = (mainFields: DerivedFields) => DerivedFields
type VolumeRule = (fields: DerivedFields) => number

const COMPOSITION_RULES: Record<string, CompositionRule> = {
  'Flywheel_Rim->Shaft': (rim) => ({
    diameter_m: rim.inner_diameter_m * 0.95,
    length_m: rim.thickness_m * 3,
  }),
  'Flywheel_Rim->Bearing_Housing': (rim) => {
    const shaftD = rim.inner_diameter_m * 0.95
    return {
      bore_diameter_m: shaftD * 1.01,
      outer_diameter_m: shaftD * 2.5,
    }
  },
  'Pelton_Runner->Shaft': (p) => ({
    diameter_m: p.runner_diameter_m * 0.15,
    length_m: p.runner_diameter_m * 1.5,
  }),
  'Pelton_Runner->Housing': (p) => ({
    inner_diameter_m: p.runner_diameter_m * 1.3,
    wall_thickness_m: 0.01,
  }),
  'Pelton_Runner->Mounting_Frame': (p) => ({
    length_m: p.runner_diameter_m * 2,
    width_m: p.runner_diameter_m * 1.6,
    height_m: 0.1,
  }),
  'Hinge_Panel->Tensor_Rod': (p) => ({
    length_m: p.height_m * 1.1,
    diameter_m: 0.01,
  }),
  'Hinge_Panel->Base_Connector': (p) => ({
    width_m: p.thickness_m * 2,
    height_m: 0.02,
  }),
}

const VOLUME_RULES: Record<string, VolumeRule> = {
  Flywheel_Rim: (f) =>
    (Math.PI / 4) *
    (Math.pow(f.outer_diameter_m, 2) - Math.pow(f.inner_diameter_m, 2)) *
    f.thickness_m,
  Shaft: (f) => (Math.PI / 4) * Math.pow(f.diameter_m, 2) * f.length_m,
  Bearing_Housing: (f) => {
    // Approx hollow cylinder, length ≈ outer × 0.5 (rough heuristic for visual mass share)
    const length = f.outer_diameter_m * 0.5
    return (Math.PI / 4) * (Math.pow(f.outer_diameter_m, 2) - Math.pow(f.bore_diameter_m, 2)) * length
  },
  Pelton_Runner: (f) => {
    // Disc minus 20 bucket cavities (matches builder docstring)
    const D = f.runner_diameter_m
    const thickness = 0.1 * D
    const disc = (Math.PI / 4) * D * D * thickness
    const bucketR = 0.06 * D
    const buckets = (f.bucket_count ?? 20) * Math.PI * bucketR * bucketR * thickness
    return Math.max(disc - buckets, disc * 0.5)
  },
  Housing: (f) => {
    // Thin cylindrical shell, height ≈ inner diameter for a rough estimate
    const h = f.inner_diameter_m
    const t = f.wall_thickness_m
    return Math.PI * (f.inner_diameter_m + t) * t * h
  },
  Mounting_Frame: (f) => f.length_m * f.width_m * f.height_m,
  Hinge_Panel: (f) => f.width_m * f.height_m * f.thickness_m,
  Tensor_Rod: (f) => (Math.PI / 4) * Math.pow(f.diameter_m, 2) * f.length_m,
  Base_Connector: (f) => f.width_m * f.height_m * f.width_m,
}

function extractNumericFields(intent: DesignIntent): DerivedFields {
  const out: DerivedFields = {}
  for (const [name, field] of Object.entries(intent.fields)) {
    if (typeof field.value === 'number') {
      out[name] = field.value
    } else if (typeof field.value === 'string') {
      const n = Number(field.value)
      if (Number.isFinite(n)) out[name] = n
    }
  }
  return out
}

/**
 * Derive every part in the assembly (main + composed) with its dimensions
 * and approximate volume. Returns [] if required main fields are missing.
 */
export function derivePartsFromIntent(intent: DesignIntent | null): PartSummary[] {
  if (!intent) return []
  const mainFields = extractNumericFields(intent)
  const mainVolumeRule = VOLUME_RULES[intent.type]
  if (!mainVolumeRule) return []

  let mainVolume: number
  try {
    mainVolume = mainVolumeRule(mainFields)
    if (!Number.isFinite(mainVolume) || mainVolume <= 0) return []
  } catch {
    return []
  }

  const parts: PartSummary[] = [
    { name: intent.type, role: 'main', fields: mainFields, volume_m3: mainVolume },
  ]

  for (const composed of intent.composed_of ?? []) {
    const ruleKey = `${intent.type}->${composed}`
    const rule = COMPOSITION_RULES[ruleKey]
    const volRule = VOLUME_RULES[composed]
    if (!rule || !volRule) continue
    try {
      const composedFields = rule(mainFields)
      const volume = volRule(composedFields)
      if (!Number.isFinite(volume) || volume <= 0) continue
      parts.push({ name: composed, role: 'composed', fields: composedFields, volume_m3: volume })
    } catch {
      // Skip parts whose rule throws (e.g. NaN inputs)
    }
  }

  return parts
}

/**
 * Apportion a known total mass across parts proportionally to their volume.
 * Used when the backend reports only an assembly-level mass but we still want
 * a per-part mass column in the UI.
 */
export function apportionMass(parts: PartSummary[], totalMassKg: number): Array<PartSummary & { mass_kg: number }> {
  const totalVolume = parts.reduce((sum, p) => sum + p.volume_m3, 0)
  if (totalVolume <= 0) {
    return parts.map((p) => ({ ...p, mass_kg: 0 }))
  }
  return parts.map((p) => ({ ...p, mass_kg: totalMassKg * (p.volume_m3 / totalVolume) }))
}

/**
 * Format the most representative dimension(s) for a part as a short string,
 * e.g. "Ø0.60 × 0.05 m" for a disc or "Ø0.10 · L 0.15 m" for a shaft.
 */
export function formatDimensions(part: PartSummary): string {
  const f = part.fields
  switch (part.name) {
    case 'Flywheel_Rim':
      return `Ø${f.outer_diameter_m.toFixed(2)} × ${f.thickness_m.toFixed(3)} m`
    case 'Shaft':
      return `Ø${f.diameter_m.toFixed(3)} · L ${f.length_m.toFixed(3)} m`
    case 'Bearing_Housing':
      return `Ø${f.outer_diameter_m.toFixed(3)} · bore Ø${f.bore_diameter_m.toFixed(3)} m`
    case 'Pelton_Runner':
      return `Ø${f.runner_diameter_m.toFixed(2)} · ${f.bucket_count ?? '?'} buckets`
    case 'Housing':
      return `Ø${f.inner_diameter_m.toFixed(2)} · wall ${(f.wall_thickness_m * 1000).toFixed(0)}mm`
    case 'Mounting_Frame':
      return `${f.length_m.toFixed(2)} × ${f.width_m.toFixed(2)} × ${f.height_m.toFixed(2)} m`
    case 'Hinge_Panel':
      return `${f.width_m.toFixed(2)} × ${f.height_m.toFixed(2)} × ${f.thickness_m.toFixed(3)} m`
    case 'Tensor_Rod':
      return `Ø${(f.diameter_m * 1000).toFixed(0)}mm · L ${f.length_m.toFixed(2)} m`
    case 'Base_Connector':
      return `${f.width_m.toFixed(3)} × ${f.height_m.toFixed(3)} m`
    default:
      return ''
  }
}
