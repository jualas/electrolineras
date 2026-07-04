import { fetchApi } from './client'
import type { AlongRouteResponse, GeocodeResult, NearbyReferenceResponse, RoutePreference, Station } from './types'
import { stationToFeature } from './stationFeature'

export type AlongRouteQuery = {
  originLat: number
  originLon: number
  destLat: number
  destLon: number
  minKw?: number
  maxKw?: number
  corridorKm?: number
  limit?: number
  routePreference?: RoutePreference
  avoidHighways?: boolean
}

export async function geocodePlace(query: string): Promise<GeocodeResult> {
  const params = new URLSearchParams({
    q: query.trim(),
    limit: '1',
  })
  const payload = await fetchApi<NearbyReferenceResponse & { results: unknown[] }>(
    `/api/v1/stations/nearby?${params.toString()}`,
  )
  return {
    lat: payload.reference.lat,
    lon: payload.reference.lon,
    label: payload.reference_label ?? query.trim(),
  }
}

export async function fetchGeocodeSuggestions(query: string, limit = 5): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({
    q: query.trim(),
    limit: String(limit),
  })
  return fetchApi<GeocodeResult[]>(`/api/v1/meta/geocode?${params.toString()}`)
}

export async function fetchAlongRoute(
  query: AlongRouteQuery,
  init?: RequestInit,
): Promise<AlongRouteResponse> {
  const params = new URLSearchParams({
    origin_lat: String(query.originLat),
    origin_lon: String(query.originLon),
    dest_lat: String(query.destLat),
    dest_lon: String(query.destLon),
    include_route: 'true',
  })

  if (query.minKw !== undefined) {
    params.set('min_kw', String(query.minKw))
  }
  if (query.maxKw !== undefined) {
    params.set('max_kw', String(query.maxKw))
  }
  if (query.corridorKm !== undefined) {
    params.set('corridor_km', String(query.corridorKm))
  }
  if (query.limit !== undefined) {
    params.set('limit', String(query.limit))
  }
  if (query.routePreference !== undefined) {
    params.set('route_preference', query.routePreference)
  }
  if (query.avoidHighways) {
    params.set('avoid_highways', 'true')
  }

  return fetchApi<AlongRouteResponse>(`/api/v1/stations/along-route?${params.toString()}`, init)
}

export { stationToFeature }

export function alongRouteToFeatures(results: AlongRouteResponse['results']) {
  return results.map((item) => stationToFeature(item.station))
}

export function stationLabel(station: Station): string {
  return station.site_name ?? station.operator ?? station.id
}
