import { fetchApi } from './client'
import type { Station } from './types'

export type NearestLiveResponse = {
  reference: { lat: number; lon: number }
  radius_m: number
  min_kw: number
  used_min_kw: number
  station: Station | null
  distance_m: number | null
  distance_km: number | null
  access_class: string | null
}

export type NearestLiveQuery = {
  lat: number
  lon: number
  radiusM?: number
  minKw?: number
  maxKw?: number
  publicOpenOnly?: boolean
  adHocOnly?: boolean
  excludeParking?: boolean
}

export async function fetchNearestLive(
  query: NearestLiveQuery,
  init?: RequestInit,
): Promise<NearestLiveResponse> {
  const params = new URLSearchParams()
  params.set('lat', String(query.lat))
  params.set('lon', String(query.lon))
  if (query.radiusM !== undefined) {
    params.set('radius_m', String(query.radiusM))
  }
  if (query.minKw !== undefined) {
    params.set('min_kw', String(query.minKw))
  }
  if (query.maxKw !== undefined) {
    params.set('max_kw', String(query.maxKw))
  }
  if (query.publicOpenOnly !== undefined) {
    params.set('public_open_only', query.publicOpenOnly ? 'true' : 'false')
  }
  if (query.adHocOnly) {
    params.set('ad_hoc_only', 'true')
  }
  if (query.excludeParking) {
    params.set('exclude_parking', 'true')
  }
  return fetchApi<NearestLiveResponse>(`/api/v1/stations/nearest-live?${params.toString()}`, init)
}
