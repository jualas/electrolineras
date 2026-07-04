import type { RouteLineGeometry, RoutePreference } from '../api/types'

export type RouteVariantGeometries = {
  shortest?: RouteLineGeometry | null
  fastest?: RouteLineGeometry | null
  conventional?: RouteLineGeometry | null
}

export function routeVariantGeometriesFromResponse(data: {
  route_shortest_geometry?: RouteLineGeometry | null
  route_fastest_geometry?: RouteLineGeometry | null
  route_conventional_geometry?: RouteLineGeometry | null
}): RouteVariantGeometries {
  return {
    shortest: data.route_shortest_geometry ?? null,
    fastest: data.route_fastest_geometry ?? null,
    conventional: data.route_conventional_geometry ?? null,
  }
}

export function hasRouteComparison(geometries: RouteVariantGeometries): boolean {
  const keys = (['shortest', 'fastest'] as const).filter((key) => geometries[key])
  return keys.length >= 2
}

export function activeRouteGeometry(
  preference: RoutePreference | null | undefined,
  geometries: RouteVariantGeometries,
  fallback: RouteLineGeometry | null | undefined,
): RouteLineGeometry | null {
  if (preference && geometries[preference]) {
    return geometries[preference] ?? null
  }
  return fallback ?? null
}

export function inactiveRouteGeometries(
  preference: RoutePreference | null | undefined,
  geometries: RouteVariantGeometries,
): RouteLineGeometry[] {
  const inactive: RouteLineGeometry[] = []
  for (const key of ['shortest', 'fastest', 'conventional'] as const) {
    if (key === preference) {
      continue
    }
    const geometry = geometries[key]
    if (geometry) {
      inactive.push(geometry)
    }
  }
  return inactive
}

export function combinedRouteBounds(geometries: RouteLineGeometry[]): [number, number][] {
  const points: [number, number][] = []
  for (const geometry of geometries) {
    for (const coord of geometry.coordinates) {
      points.push(coord)
    }
  }
  return points
}
