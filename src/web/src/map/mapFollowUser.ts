/** Distancia mínima (m) para recentrar el mapa al moverse. */
export const MAP_RECENTER_MIN_MOVE_M = 80

/** Zoom mínimo al seguir al usuario durante viaje activo. */
export const MAP_FOLLOW_ZOOM = 13.5

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180
}

export function haversineMeters(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const earthRadius = 6371000
  const dLat = toRadians(b.lat - a.lat)
  const dLon = toRadians(b.lon - a.lon)
  const lat1 = toRadians(a.lat)
  const lat2 = toRadians(b.lat)
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * earthRadius * Math.asin(Math.sqrt(h))
}

export function shouldRecenterMapOnUserMove(
  previous: { lat: number; lon: number } | null,
  next: { lat: number; lon: number },
  minMoveM = MAP_RECENTER_MIN_MOVE_M,
): boolean {
  if (!previous) {
    return true
  }
  return haversineMeters(previous, next) >= minMoveM
}
