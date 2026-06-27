import maplibregl from 'maplibre-gl'

import type { LatLon } from '../api/types'
import { CLUSTER_LAYER_ID } from './stationLayers'

export const CITY_REFERENCE_SOURCE_ID = 'city-reference'
export const CITY_RADIUS_SOURCE_ID = 'city-radius'
export const CITY_REFERENCE_LAYER_ID = 'city-reference-point'
export const CITY_RADIUS_LAYER_ID = 'city-radius-fill'
export const CITY_RADIUS_LINE_LAYER_ID = 'city-radius-line'

type ThemeMode = 'light' | 'dark'

function cityColors(theme: ThemeMode) {
  if (theme === 'dark') {
    return {
      point: '#d2a8ff',
      fill: 'rgba(210, 168, 255, 0.12)',
      line: 'rgba(210, 168, 255, 0.55)',
    }
  }
  return {
    point: '#8250df',
    fill: 'rgba(130, 80, 223, 0.12)',
    line: 'rgba(130, 80, 223, 0.45)',
  }
}

function circlePolygon(lon: number, lat: number, radiusM: number, steps = 64): [number, number][] {
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

export function ensureCityLayers(map: maplibregl.Map, theme: ThemeMode): void {
  if (!map.getSource(CITY_REFERENCE_SOURCE_ID)) {
    map.addSource(CITY_REFERENCE_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  if (!map.getSource(CITY_RADIUS_SOURCE_ID)) {
    map.addSource(CITY_RADIUS_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  }

  const colors = cityColors(theme)
  const beforeLayer = map.getLayer(CLUSTER_LAYER_ID) ? CLUSTER_LAYER_ID : undefined

  if (!map.getLayer(CITY_RADIUS_LAYER_ID)) {
    map.addLayer(
      {
        id: CITY_RADIUS_LAYER_ID,
        type: 'fill',
        source: CITY_RADIUS_SOURCE_ID,
        paint: {
          'fill-color': colors.fill,
          'fill-opacity': 1,
        },
      },
      beforeLayer,
    )
  }

  if (!map.getLayer(CITY_RADIUS_LINE_LAYER_ID)) {
    map.addLayer(
      {
        id: CITY_RADIUS_LINE_LAYER_ID,
        type: 'line',
        source: CITY_RADIUS_SOURCE_ID,
        paint: {
          'line-color': colors.line,
          'line-width': 2,
        },
      },
      beforeLayer,
    )
  }

  if (!map.getLayer(CITY_REFERENCE_LAYER_ID)) {
    map.addLayer(
      {
        id: CITY_REFERENCE_LAYER_ID,
        type: 'circle',
        source: CITY_REFERENCE_SOURCE_ID,
        paint: {
          'circle-color': colors.point,
          'circle-radius': 9,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      },
      beforeLayer,
    )
  }
}

export function updateCityLayerTheme(map: maplibregl.Map, theme: ThemeMode): void {
  if (!map.getLayer(CITY_REFERENCE_LAYER_ID)) {
    return
  }
  const colors = cityColors(theme)
  map.setPaintProperty(CITY_REFERENCE_LAYER_ID, 'circle-color', colors.point)
  map.setPaintProperty(CITY_RADIUS_LAYER_ID, 'fill-color', colors.fill)
  map.setPaintProperty(CITY_RADIUS_LINE_LAYER_ID, 'line-color', colors.line)
}

export function setCityReference(map: maplibregl.Map, reference: LatLon | null): void {
  const source = map.getSource(CITY_REFERENCE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  if (!reference) {
    source.setData({ type: 'FeatureCollection', features: [] })
    return
  }
  source.setData({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Point', coordinates: [reference.lon, reference.lat] },
  })
}

export function setCityRadiusCircle(map: maplibregl.Map, reference: LatLon | null, radiusM: number | null): void {
  const source = map.getSource(CITY_RADIUS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (!source) {
    return
  }
  if (!reference || radiusM === null || radiusM <= 0) {
    source.setData({ type: 'FeatureCollection', features: [] })
    return
  }
  const ring = circlePolygon(reference.lon, reference.lat, radiusM)
  source.setData({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [ring] },
  })
}

export function clearCityOverlay(map: maplibregl.Map): void {
  setCityReference(map, null)
  setCityRadiusCircle(map, null, null)
}

export function fitMapToCityReference(
  map: maplibregl.Map,
  reference: LatLon,
  radiusM: number | null,
  padding = 56,
): void {
  if (radiusM !== null && radiusM > 0) {
    const ring = circlePolygon(reference.lon, reference.lat, radiusM)
    const bounds = new maplibregl.LngLatBounds()
    for (const [lon, lat] of ring) {
      bounds.extend([lon, lat])
    }
    map.fitBounds(bounds, { padding, maxZoom: 15, duration: 700 })
    return
  }
  map.flyTo({ center: [reference.lon, reference.lat], zoom: 13, duration: 700 })
}

export function fitMapToBbox(
  map: maplibregl.Map,
  west: number,
  south: number,
  east: number,
  north: number,
  padding = 48,
): void {
  map.fitBounds(
    [
      [west, south],
      [east, north],
    ],
    { padding, duration: 700 },
  )
}
