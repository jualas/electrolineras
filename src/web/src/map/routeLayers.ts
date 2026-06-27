import maplibregl from 'maplibre-gl'

import type { LatLon, RouteLineGeometry } from '../api/types'
import { CLUSTER_LAYER_ID, POINT_LAYER_ID } from './stationLayers'

export const ROUTE_SOURCE_ID = 'route-line'
export const ROUTE_LAYER_ID = 'route-line-layer'
export const ROUTE_ORIGIN_LAYER_ID = 'route-origin'
export const ROUTE_DEST_LAYER_ID = 'route-destination'
export const ROUTE_ENDPOINTS_SOURCE_ID = 'route-endpoints'
export const RANGE_SOURCE_ID = 'route-range'
export const RANGE_LAYER_ID = 'route-range-layer'
export const RANGE_OUTLINE_LAYER_ID = 'route-range-outline'

type ThemeMode = 'light' | 'dark'

function routeColors(theme: ThemeMode) {
  if (theme === 'dark') {
    return {
      line: '#5fd4ff',
      origin: '#7ee787',
      destination: '#ff7b72',
    }
  }
  return {
    line: '#0d7ea6',
    origin: '#1a7f37',
    destination: '#cf222e',
  }
}

export function ensureRouteLayers(map: maplibregl.Map, theme: ThemeMode): void {
  if (!map.getSource(ROUTE_SOURCE_ID)) {
    map.addSource(ROUTE_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  if (!map.getSource(ROUTE_ENDPOINTS_SOURCE_ID)) {
    map.addSource(ROUTE_ENDPOINTS_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  if (!map.getSource(RANGE_SOURCE_ID)) {
    map.addSource(RANGE_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  const colors = routeColors(theme)

  if (!map.getLayer(ROUTE_LAYER_ID)) {
    map.addLayer(
      {
        id: ROUTE_LAYER_ID,
        type: 'line',
        source: ROUTE_SOURCE_ID,
        paint: {
          'line-color': colors.line,
          'line-width': 4,
          'line-opacity': 0.85,
        },
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
      },
      map.getLayer(CLUSTER_LAYER_ID) ? CLUSTER_LAYER_ID : undefined,
    )
  }

  const endpointBefore = map.getLayer(POINT_LAYER_ID) ? undefined : CLUSTER_LAYER_ID

  if (!map.getLayer(ROUTE_ORIGIN_LAYER_ID)) {
    map.addLayer(
      {
        id: ROUTE_ORIGIN_LAYER_ID,
        type: 'circle',
        source: ROUTE_ENDPOINTS_SOURCE_ID,
        filter: ['==', ['get', 'role'], 'origin'],
        paint: {
          'circle-color': colors.origin,
          'circle-radius': 8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      },
      endpointBefore,
    )
  }

  if (!map.getLayer(ROUTE_DEST_LAYER_ID)) {
    map.addLayer(
      {
        id: ROUTE_DEST_LAYER_ID,
        type: 'circle',
        source: ROUTE_ENDPOINTS_SOURCE_ID,
        filter: ['==', ['get', 'role'], 'destination'],
        paint: {
          'circle-color': colors.destination,
          'circle-radius': 8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      },
      endpointBefore,
    )
  }

  if (!map.getLayer(RANGE_LAYER_ID)) {
    map.addLayer(
      {
        id: RANGE_LAYER_ID,
        type: 'fill',
        source: RANGE_SOURCE_ID,
        paint: {
          'fill-color': colors.origin,
          'fill-opacity': 0.08,
        },
      },
      ROUTE_LAYER_ID,
    )
  }

  if (!map.getLayer(RANGE_OUTLINE_LAYER_ID)) {
    map.addLayer(
      {
        id: RANGE_OUTLINE_LAYER_ID,
        type: 'line',
        source: RANGE_SOURCE_ID,
        paint: {
          'line-color': colors.origin,
          'line-width': 1.5,
          'line-opacity': 0.35,
          'line-dasharray': [2, 2],
        },
      },
      ROUTE_LAYER_ID,
    )
  }
}

export function updateRouteLayerTheme(map: maplibregl.Map, theme: ThemeMode): void {
  if (!map.getLayer(ROUTE_LAYER_ID)) {
    return
  }
  const colors = routeColors(theme)
  map.setPaintProperty(ROUTE_LAYER_ID, 'line-color', colors.line)
  if (map.getLayer(ROUTE_DEST_LAYER_ID)) {
    map.setPaintProperty(ROUTE_DEST_LAYER_ID, 'circle-color', colors.destination)
  }
  if (map.getLayer(RANGE_LAYER_ID)) {
    map.setPaintProperty(RANGE_LAYER_ID, 'fill-color', colors.origin)
  }
  if (map.getLayer(RANGE_OUTLINE_LAYER_ID)) {
    map.setPaintProperty(RANGE_OUTLINE_LAYER_ID, 'line-color', colors.origin)
  }
}

export function setRouteLine(map: maplibregl.Map, geometry: RouteLineGeometry | null): void {
  const source = map.getSource(ROUTE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  if (!geometry) {
    source.setData({ type: 'FeatureCollection', features: [] })
    return
  }
  source.setData({
    type: 'Feature',
    properties: {},
    geometry,
  })
}

export function setRouteEndpoints(map: maplibregl.Map, origin: LatLon | null, destination: LatLon | null): void {
  const source = map.getSource(ROUTE_ENDPOINTS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  const features = []
  if (origin) {
    features.push({
      type: 'Feature' as const,
      properties: { role: 'origin' },
      geometry: { type: 'Point' as const, coordinates: [origin.lon, origin.lat] },
    })
  }
  if (destination) {
    features.push({
      type: 'Feature' as const,
      properties: { role: 'destination' },
      geometry: { type: 'Point' as const, coordinates: [destination.lon, destination.lat] },
    })
  }
  source.setData({ type: 'FeatureCollection', features })
}

export function clearRouteOverlay(map: maplibregl.Map): void {
  setRouteLine(map, null)
  setRouteEndpoints(map, null, null)
  setRangeCircle(map, null, null)
}

function circleRingCoordinates(
  lat: number,
  lon: number,
  radiusKm: number,
  points = 64,
): [number, number][] {
  const coordinates: [number, number][] = []
  const latRad = (lat * Math.PI) / 180
  const kmPerDegreeLat = 111.32
  const kmPerDegreeLon = Math.max(0.01, 111.32 * Math.cos(latRad))

  for (let index = 0; index <= points; index += 1) {
    const angle = (index / points) * 2 * Math.PI
    const pointLat = lat + (radiusKm / kmPerDegreeLat) * Math.sin(angle)
    const pointLon = lon + (radiusKm / kmPerDegreeLon) * Math.cos(angle)
    coordinates.push([pointLon, pointLat])
  }
  return coordinates
}

export function setRangeCircle(map: maplibregl.Map, center: LatLon | null, radiusKm: number | null): void {
  const source = map.getSource(RANGE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  if (!center || radiusKm == null || radiusKm <= 0) {
    source.setData({ type: 'FeatureCollection', features: [] })
    return
  }
  source.setData({
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [circleRingCoordinates(center.lat, center.lon, radiusKm)],
    },
  })
}

export function fitMapToRoute(map: maplibregl.Map, geometry: RouteLineGeometry, padding = 48): void {
  const bounds = new maplibregl.LngLatBounds()
  for (const [lon, lat] of geometry.coordinates) {
    bounds.extend([lon, lat])
  }
  map.fitBounds(bounds, { padding, maxZoom: 11, duration: 800 })
}
