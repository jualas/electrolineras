import type { RouteLineGeometry } from '../api/types'
import type { MapCoords } from '../navigation/externalMaps'
import { haversineKm } from './planRouteStops'

export const ROUTE_DEVIATION_KM_THRESHOLD = 2

/** Distancia mínima de un punto a un segmento geodésico (aprox. plana local). */
function pointToSegmentKm(point: MapCoords, a: MapCoords, b: MapCoords): number {
  const dx = b.lon - a.lon
  const dy = b.lat - a.lat
  if (dx === 0 && dy === 0) {
    return haversineKm(point, a)
  }
  const t = Math.max(
    0,
    Math.min(1, ((point.lon - a.lon) * dx + (point.lat - a.lat) * dy) / (dx * dx + dy * dy)),
  )
  const projection = { lat: a.lat + t * dy, lon: a.lon + t * dx }
  return haversineKm(point, projection)
}

/** Distancia mínima del punto a la polilínea OSRM (coordenadas GeoJSON lon,lat). */
export function distancePointToRouteKm(point: MapCoords, geometry: RouteLineGeometry | null): number | null {
  if (!geometry?.coordinates?.length) {
    return null
  }
  const coords = geometry.coordinates
  let minKm = Infinity
  for (let index = 0; index < coords.length - 1; index += 1) {
    const [lonA, latA] = coords[index]
    const [lonB, latB] = coords[index + 1]
    const segmentKm = pointToSegmentKm(point, { lat: latA, lon: lonA }, { lat: latB, lon: lonB })
    if (segmentKm < minKm) {
      minKm = segmentKm
    }
  }
  if (coords.length === 1) {
    const [lon, lat] = coords[0]
    return haversineKm(point, { lat, lon })
  }
  return Number.isFinite(minKm) ? minKm : null
}

export function isOffRoute(point: MapCoords, geometry: RouteLineGeometry | null, thresholdKm = ROUTE_DEVIATION_KM_THRESHOLD): boolean {
  const distanceKm = distancePointToRouteKm(point, geometry)
  return distanceKm != null && distanceKm > thresholdKm
}
