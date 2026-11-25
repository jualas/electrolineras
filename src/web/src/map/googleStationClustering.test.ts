import { describe, expect, it } from 'vitest'

import type { StationFeature } from '../api/types'
import { clusterStationsForZoom, stationMarkerColor } from './googleStationClustering'

function makeFeature(id: string, lat: number, lon: number, props: Record<string, unknown> = {}): StationFeature {
  return {
    type: 'Feature',
    id,
    geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: {
      id,
      site_name: `Estación ${id}`,
      operator: 'Demo',
      max_power_kw: 150,
      connector_count: 2,
      country: 'ES',
      ...props,
    },
  } as StationFeature
}

describe('googleStationClustering', () => {
  it('agrupa puntos cercanos en zoom bajo y expande en zoom alto', () => {
    const many: StationFeature[] = []
    for (let i = 0; i < 80; i++) {
      many.push(makeFeature(`s-${i}`, 37.18 + (i % 5) * 0.002, -3.6 + Math.floor(i / 5) * 0.002))
    }

    const lowZoom = clusterStationsForZoom(many, 6)
    expect(lowZoom.length).toBeLessThan(many.length)
    expect(lowZoom.some((item) => item.kind === 'cluster')).toBe(true)

    const highZoom = clusterStationsForZoom(many, 13)
    expect(highZoom.length).toBe(80)
    expect(highZoom.every((item) => item.kind === 'point')).toBe(true)
  })

  it('elige colores coherentes para paradas planificadas y estados REVE', () => {
    expect(stationMarkerColor({ planned_stop_order: 1 }, null)).toBe('#2563eb')
    expect(stationMarkerColor({ planned_stop_order: 1 }, 1)).toBe('#ea580c')
    expect(stationMarkerColor({ dynamic_status: 'AVAILABLE' })).toBe('#1a8f4a')
    expect(stationMarkerColor({ dynamic_status: 'CHARGING' })).toBe('#c47a00')
    expect(stationMarkerColor({ dynamic_status: 'OUTOFORDER' })).toBe('#c0392b')
    expect(stationMarkerColor({ charging_classification: 'critical' })).toBe('#c0392b')
    expect(stationMarkerColor({})).toBe('#0d7ea6')
  })
})
