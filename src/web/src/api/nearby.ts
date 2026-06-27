import { fetchApi } from './client'
import type { MapBounds, NearbyResponse } from './types'

export type NearbyQuery = {
  lat?: number
  lon?: number
  q?: string
  bbox?: MapBounds
  radiusM?: number
  minKw?: number
  maxKw?: number
  publicOpenOnly?: boolean
  excludeCommercial?: boolean
  adHocOnly?: boolean
  limit?: number
}

function bboxParam(bounds: MapBounds): string {
  return `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`
}

export async function fetchNearbyStations(query: NearbyQuery, init?: RequestInit): Promise<NearbyResponse> {
  const params = new URLSearchParams()

  if (query.lat !== undefined && query.lon !== undefined) {
    params.set('lat', String(query.lat))
    params.set('lon', String(query.lon))
  }
  if (query.q) {
    params.set('q', query.q.trim())
  }
  if (query.bbox) {
    params.set('bbox', bboxParam(query.bbox))
  }
  if (query.radiusM !== undefined) {
    params.set('radius_m', String(query.radiusM))
  }
  if (query.minKw !== undefined) {
    params.set('min_kw', String(query.minKw))
  }
  if (query.maxKw !== undefined) {
    params.set('max_kw', String(query.maxKw))
  }
  if (query.publicOpenOnly) {
    params.set('public_open_only', 'true')
  }
  if (query.excludeCommercial) {
    params.set('exclude_commercial', 'true')
  }
  if (query.adHocOnly) {
    params.set('ad_hoc_only', 'true')
  }
  if (query.limit !== undefined) {
    params.set('limit', String(query.limit))
  }

  return fetchApi<NearbyResponse>(`/api/v1/stations/nearby?${params.toString()}`, init)
}

export function formatDistanceKm(distanceKm: number, distanceM: number): string {
  if (distanceKm < 1) {
    return `${Math.round(distanceM)} m`
  }
  return `${distanceKm.toFixed(1)} km`
}
