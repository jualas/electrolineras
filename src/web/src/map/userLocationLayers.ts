import maplibregl from 'maplibre-gl'

export const USER_LOCATION_SOURCE_ID = 'user-location'
export const USER_LOCATION_ACCURACY_LAYER_ID = 'user-location-accuracy'
export const USER_LOCATION_DOT_LAYER_ID = 'user-location-dot'
export const USER_LOCATION_PULSE_LAYER_ID = 'user-location-pulse'

const USER_COLORS = {
  accuracy: 'rgba(26, 115, 232, 0.15)',
  accuracyLine: 'rgba(26, 115, 232, 0.35)',
  dot: '#1a73e8',
  pulse: 'rgba(26, 115, 232, 0.25)',
}

function circlePolygon(lon: number, lat: number, radiusM: number, steps = 48): [number, number][] {
  const coordinates: [number, number][] = []
  const earthRadius = 6371000
  for (let step = 0; step <= steps; step += 1) {
    const angle = (step / steps) * 2 * Math.PI
    const dx = radiusM * Math.cos(angle)
    const dy = radiusM * Math.sin(angle)
    const latOffset = (dy / earthRadius) * (180 / Math.PI)
    const lonOffset = (dx / (earthRadius * Math.cos((lat * Math.PI) / 180))) * (180 / Math.PI)
    coordinates.push([lon + lonOffset, lat + latOffset])
  }
  return coordinates
}

export function ensureUserLocationLayers(map: maplibregl.Map): void {
  if (!map.getSource(USER_LOCATION_SOURCE_ID)) {
    map.addSource(USER_LOCATION_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  if (!map.getLayer(USER_LOCATION_ACCURACY_LAYER_ID)) {
    map.addLayer({
      id: USER_LOCATION_ACCURACY_LAYER_ID,
      type: 'fill',
      source: USER_LOCATION_SOURCE_ID,
      filter: ['==', ['get', 'kind'], 'accuracy'],
      paint: {
        'fill-color': USER_COLORS.accuracy,
        'fill-opacity': 1,
      },
    })
  }

  if (!map.getLayer(USER_LOCATION_PULSE_LAYER_ID)) {
    map.addLayer({
      id: USER_LOCATION_PULSE_LAYER_ID,
      type: 'circle',
      source: USER_LOCATION_SOURCE_ID,
      filter: ['==', ['get', 'kind'], 'dot'],
      paint: {
        'circle-radius': 14,
        'circle-color': USER_COLORS.pulse,
        'circle-opacity': 0.6,
      },
    })
  }

  if (!map.getLayer(USER_LOCATION_DOT_LAYER_ID)) {
    map.addLayer({
      id: USER_LOCATION_DOT_LAYER_ID,
      type: 'circle',
      source: USER_LOCATION_SOURCE_ID,
      filter: ['==', ['get', 'kind'], 'dot'],
      paint: {
        'circle-radius': 7,
        'circle-color': USER_COLORS.dot,
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
      },
    })
  }
}

export function setUserLocationMarker(
  map: maplibregl.Map,
  point: { lat: number; lon: number; accuracyM?: number | null } | null,
): void {
  ensureUserLocationLayers(map)
  const source = map.getSource(USER_LOCATION_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  if (!point) {
    source.setData({ type: 'FeatureCollection', features: [] })
    return
  }

  const features: Array<{
    type: 'Feature'
    properties: { kind: string }
    geometry:
      | { type: 'Point'; coordinates: [number, number] }
      | { type: 'Polygon'; coordinates: [number, number][][] }
  }> = [
    {
      type: 'Feature',
      properties: { kind: 'dot' },
      geometry: {
        type: 'Point',
        coordinates: [point.lon, point.lat],
      },
    },
  ]

  const accuracyM = point.accuracyM
  if (accuracyM != null && Number.isFinite(accuracyM) && accuracyM > 0) {
    features.push({
      type: 'Feature',
      properties: { kind: 'accuracy' },
      geometry: {
        type: 'Polygon',
        coordinates: [circlePolygon(point.lon, point.lat, accuracyM)],
      },
    })
  }

  source.setData({ type: 'FeatureCollection', features })
}

export function clearUserLocationMarker(map: maplibregl.Map): void {
  setUserLocationMarker(map, null)
}
