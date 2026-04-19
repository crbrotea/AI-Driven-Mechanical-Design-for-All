'use client'
import { useTranslations } from 'next-intl'
import type { MassProperties } from '@/lib/types'

export function MassPanel({ properties }: { properties: MassProperties }) {
  const t = useTranslations('viewer')
  const [minX, minY, minZ, maxX, maxY, maxZ] = properties.bbox_m
  const dimX = (maxX - minX).toFixed(3)
  const dimY = (maxY - minY).toFixed(3)
  const dimZ = (maxZ - minZ).toFixed(3)

  return (
    <div className="absolute bottom-4 left-4 rounded-md border border-border bg-background/90 p-3 text-xs shadow">
      <div>
        <strong>{t('mass')}:</strong> {properties.mass_kg.toFixed(1)} kg
      </div>
      <div>
        <strong>{t('volume')}:</strong> {properties.volume_m3.toFixed(4)} m³
      </div>
      <div>
        <strong>{t('bbox')}:</strong> {dimX} × {dimY} × {dimZ} m
      </div>
    </div>
  )
}
