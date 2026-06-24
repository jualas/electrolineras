import { fetchApi } from './client'
import type { GeoJSONStationCollection, MapBounds, StationQuery } from './types'

function bboxParam(bounds: MapBounds): string {
  return `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`
}

export async function fetchStationsGeoJSON(
  query: StationQuery,
  init?: RequestInit,
): Promise<GeoJSONStationCollection> {
  const params = new URLSearchParams({
    format: 'geojson',
    bbox: bboxParam(query.bbox),
    limit: String(query.limit ?? 5000),
  })

  if (query.minKw !== undefined) {
    params.set('min_kw', String(query.minKw))
  }
  if (query.maxKw !== undefined) {
    params.set('max_kw', String(query.maxKw))
  }
  if (query.country) {
    params.set('country', query.country)
  }

  return fetchApi<GeoJSONStationCollection>(`/api/v1/stations?${params.toString()}`, init)
}
