import type { StationFeature } from '../api/types'

export type ClusteredStationItem =
  | {
      kind: 'cluster'
      id: string
      lat: number
      lon: number
      count: number
      bounds: { west: number; south: number; east: number; north: number }
    }
  | {
      kind: 'point'
      id: string
      lat: number
      lon: number
      feature: StationFeature
    }

const DEFAULT_STATION_COLOR = '#0d7ea6'

export function stationMarkerColor(properties: Record<string, unknown>, selectedPlannedOrder?: number | null): string {
  const plannedOrder = properties.planned_stop_order
  if (plannedOrder !== null && plannedOrder !== undefined && !Number.isNaN(Number(plannedOrder))) {
    if (selectedPlannedOrder != null && Number(plannedOrder) === selectedPlannedOrder) {
      return '#ea580c'
    }
    return '#2563eb'
  }

  const chargingClass = properties.charging_classification
  if (typeof chargingClass === 'string') {
    if (chargingClass === 'safe') return '#1a8f4a'
    if (chargingClass === 'adjusted') return '#c47a00'
    if (chargingClass === 'critical') return '#c0392b'
    if (chargingClass === 'unreachable') return '#7a7a7a'
  }

  const dynamicStatus = properties.dynamic_status
  if (dynamicStatus === 'AVAILABLE') return '#1a8f4a'
  if (dynamicStatus === 'CHARGING' || dynamicStatus === 'RESERVED') return '#c47a00'
  if (dynamicStatus === 'OUTOFORDER' || dynamicStatus === 'INOPERATIVE') return '#c0392b'

  return DEFAULT_STATION_COLOR
}

/**
 * Agrupa estaciones por cuadrícula según zoom para mantener Google Maps fluido
 * incluso con miles de puntos visibles. En zoom >= 12 o con pocos puntos muestra
 * todos los marcadores individuales.
 */
export function clusterStationsForZoom(
  features: StationFeature[],
  zoom: number,
  options?: { maxIndividualWithoutCluster?: number; maxPointsWhenUnclustered?: number },
): ClusteredStationItem[] {
  const maxIndividual = options?.maxIndividualWithoutCluster ?? 60
  const maxUnclustered = options?.maxPointsWhenUnclustered ?? 450

  if (features.length === 0) {
    return []
  }

  if (zoom >= 12 || features.length <= maxIndividual) {
    const slice = features.length > maxUnclustered ? features.slice(0, maxUnclustered) : features
    return slice.map((feature, index) => {
      const [lon, lat] = feature.geometry.coordinates
      return {
        kind: 'point',
        id: String(feature.id ?? index),
        lat,
        lon,
        feature,
      }
    })
  }

  // Tamaño de celda en grados: ~55-70 px a la latitud de España.
  const cellDeg = 42 / Math.pow(2, Math.max(zoom, 4))
  const buckets = new Map<
    string,
    {
      features: StationFeature[]
      sumLat: number
      sumLon: number
      west: number
      south: number
      east: number
      north: number
    }
  >()

  for (const feature of features) {
    const [lon, lat] = feature.geometry.coordinates
    const gx = Math.floor(lon / cellDeg)
    const gy = Math.floor(lat / cellDeg)
    const key = `${gx}:${gy}`
    const existing = buckets.get(key)
    if (!existing) {
      buckets.set(key, {
        features: [feature],
        sumLat: lat,
        sumLon: lon,
        west: lon,
        south: lat,
        east: lon,
        north: lat,
      })
    } else {
      existing.features.push(feature)
      existing.sumLat += lat
      existing.sumLon += lon
      if (lon < existing.west) existing.west = lon
      if (lon > existing.east) existing.east = lon
      if (lat < existing.south) existing.south = lat
      if (lat > existing.north) existing.north = lat
    }
  }

  const out: ClusteredStationItem[] = []
  for (const [key, bucket] of buckets.entries()) {
    if (bucket.features.length === 1) {
      const only = bucket.features[0]
      const [lon, lat] = only.geometry.coordinates
      out.push({
        kind: 'point',
        id: String(only.id ?? key),
        lat,
        lon,
        feature: only,
      })
    } else {
      const count = bucket.features.length
      out.push({
        kind: 'cluster',
        id: `cluster-${key}`,
        lat: bucket.sumLat / count,
        lon: bucket.sumLon / count,
        count,
        bounds: {
          west: bucket.west,
          south: bucket.south,
          east: bucket.east,
          north: bucket.north,
        },
      })
    }
  }
  return out
}
