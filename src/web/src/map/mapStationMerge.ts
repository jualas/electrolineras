import type { MapBounds, StationFeature } from '../api/types'

export function featureId(feature: StationFeature): string {
  return String(feature.id ?? feature.properties?.id ?? '')
}

export function featureInBounds(feature: StationFeature, bounds: MapBounds): boolean {
  const [lon, lat] = feature.geometry.coordinates
  return lon >= bounds.west && lon <= bounds.east && lat >= bounds.south && lat <= bounds.north
}

export function expandMapBounds(bounds: MapBounds, paddingRatio: number): MapBounds {
  const latSpan = bounds.north - bounds.south
  const lonSpan = bounds.east - bounds.west
  const latPad = Math.max(latSpan * paddingRatio, 0.01)
  const lonPad = Math.max(lonSpan * paddingRatio, 0.01)
  return {
    west: bounds.west - lonPad,
    south: bounds.south - latPad,
    east: bounds.east + lonPad,
    north: bounds.north + latPad,
  }
}

/** Acumula estaciones al ampliar zona; las nuevas sustituyen mismas ids. */
export function extendStationFeatures(
  previous: StationFeature[],
  incoming: StationFeature[],
): StationFeature[] {
  const merged = new Map<string, StationFeature>()
  for (const feature of previous) {
    const id = featureId(feature)
    if (id) {
      merged.set(id, feature)
    }
  }
  for (const feature of incoming) {
    const id = featureId(feature)
    if (id) {
      merged.set(id, feature)
    }
  }
  return [...merged.values()]
}

/** Estaciones a pintar: viewport + margen (sin recargar al hacer zoom in). */
export function featuresForViewport(
  features: StationFeature[],
  visibleBounds: MapBounds,
  paddingRatio = 0.35,
): StationFeature[] {
  const displayBounds = expandMapBounds(visibleBounds, paddingRatio)
  return features.filter((feature) => featureInBounds(feature, displayBounds))
}

export function countFeaturesInBounds(features: StationFeature[], bounds: MapBounds): number {
  return features.filter((feature) => featureInBounds(feature, bounds)).length
}

/** ¿El viewport actual sigue dentro de lo ya descargado? */
export function viewportWithinCoverage(
  coverage: MapBounds | null,
  visibleBounds: MapBounds,
  marginRatio = 0.08,
): boolean {
  if (!coverage) {
    return false
  }
  const latPad = (coverage.north - coverage.south) * marginRatio
  const lonPad = (coverage.east - coverage.west) * marginRatio
  return (
    visibleBounds.west >= coverage.west + lonPad &&
    visibleBounds.east <= coverage.east - lonPad &&
    visibleBounds.south >= coverage.south + latPad &&
    visibleBounds.north <= coverage.north - latPad
  )
}

export function shouldFetchStations(
  coverage: MapBounds | null,
  visibleBounds: MapBounds,
  previousZoom: number | null,
  currentZoom: number,
): boolean {
  if (!viewportWithinCoverage(coverage, visibleBounds)) {
    return true
  }
  if (previousZoom !== null && currentZoom < previousZoom - 1.25) {
    return true
  }
  return false
}
