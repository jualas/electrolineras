import type maplibregl from 'maplibre-gl'

type FeatureCollection = {
  type: 'FeatureCollection'
  features: unknown[]
}

export const STATIONS_SOURCE_ID = 'stations'
export const CLUSTER_LAYER_ID = 'station-clusters'
export const CLUSTER_COUNT_LAYER_ID = 'station-cluster-count'
export const POINT_LAYER_ID = 'station-points'

type ThemeMode = 'light' | 'dark'

const EMPTY_COLLECTION: FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

function palette(theme: ThemeMode) {
  if (theme === 'dark') {
    return {
      cluster: '#3db8e8',
      clusterText: '#0f1419',
      point: '#5fd4ff',
      pointStroke: '#0f1419',
    }
  }
  return {
    cluster: '#0d7ea6',
    clusterText: '#ffffff',
    point: '#0d7ea6',
    pointStroke: '#ffffff',
  }
}

export function ensureStationLayers(map: maplibregl.Map, theme: ThemeMode): void {
  if (map.getSource(STATIONS_SOURCE_ID)) {
    return
  }

  map.addSource(STATIONS_SOURCE_ID, {
    type: 'geojson',
    data: EMPTY_COLLECTION,
    cluster: true,
    clusterMaxZoom: 13,
    clusterRadius: 48,
  })

  const colors = palette(theme)

  map.addLayer({
    id: CLUSTER_LAYER_ID,
    type: 'circle',
    source: STATIONS_SOURCE_ID,
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': colors.cluster,
      'circle-radius': ['step', ['get', 'point_count'], 16, 20, 20, 100, 26],
      'circle-opacity': 0.88,
      'circle-stroke-width': 2,
      'circle-stroke-color': colors.pointStroke,
    },
  })

  map.addLayer({
    id: CLUSTER_COUNT_LAYER_ID,
    type: 'symbol',
    source: STATIONS_SOURCE_ID,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': ['get', 'point_count_abbreviated'],
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 12,
    },
    paint: {
      'text-color': colors.clusterText,
    },
  })

  map.addLayer({
    id: POINT_LAYER_ID,
    type: 'circle',
    source: STATIONS_SOURCE_ID,
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-color': colors.point,
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 4, 10, 7, 14, 10],
      'circle-stroke-width': 1.5,
      'circle-stroke-color': colors.pointStroke,
      'circle-opacity': 0.92,
    },
  })
}

export function updateStationLayerTheme(map: maplibregl.Map, theme: ThemeMode): void {
  if (!map.getLayer(CLUSTER_LAYER_ID)) {
    return
  }
  const colors = palette(theme)
  map.setPaintProperty(CLUSTER_LAYER_ID, 'circle-color', colors.cluster)
  map.setPaintProperty(CLUSTER_LAYER_ID, 'circle-stroke-color', colors.pointStroke)
  map.setPaintProperty(CLUSTER_COUNT_LAYER_ID, 'text-color', colors.clusterText)
  map.setPaintProperty(POINT_LAYER_ID, 'circle-color', colors.point)
  map.setPaintProperty(POINT_LAYER_ID, 'circle-stroke-color', colors.pointStroke)
}

export function setStationData(map: maplibregl.Map, data: FeatureCollection): void {
  const source = map.getSource(STATIONS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
  }
}

export function stationPopupHtml(properties: Record<string, unknown>): string {
  const siteName = String(properties.site_name ?? properties.id ?? 'Estación')
  const operator = properties.operator ? String(properties.operator) : 'Operador desconocido'
  const maxKw = Number(properties.max_power_kw ?? 0)
  const connectors = Number(properties.connector_count ?? 0)
  const country = properties.country ? String(properties.country) : ''
  const address = properties.address ? String(properties.address) : ''

  const addressLine = address ? `<p class="station-popup__address">${address}</p>` : ''

  return `
    <div class="station-popup">
      <p class="station-popup__title">${escapeHtml(siteName)}</p>
      <p class="station-popup__operator">${escapeHtml(operator)}</p>
      <p class="station-popup__meta">
        <strong>${maxKw.toFixed(0)} kW</strong>
        · ${connectors} conector${connectors === 1 ? '' : 'es'}
        ${country ? ` · ${escapeHtml(country)}` : ''}
      </p>
      ${addressLine}
    </div>
  `
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}
