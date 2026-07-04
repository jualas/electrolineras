import type maplibregl from 'maplibre-gl'

type FeatureCollection = {
  type: 'FeatureCollection'
  features: unknown[]
}

export const STATIONS_SOURCE_ID = 'stations'
export const CLUSTER_LAYER_ID = 'station-clusters'
export const CLUSTER_COUNT_LAYER_ID = 'station-cluster-count'
export const POINT_LAYER_ID = 'station-points'
export const PLANNED_STOP_LABEL_LAYER_ID = 'planned-stop-labels'

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

function pointColorExpression(theme: ThemeMode): maplibregl.ExpressionSpecification {
  const colors = palette(theme)
  return [
    'case',
    ['has', 'planned_stop_order'],
    '#2563eb',
    ['has', 'charging_classification'],
    [
      'match',
      ['get', 'charging_classification'],
      'safe',
      '#1a8f4a',
      'adjusted',
      '#c47a00',
      'critical',
      '#c0392b',
      'unreachable',
      '#7a7a7a',
      colors.point,
    ],
    ['==', ['get', 'dynamic_status'], 'AVAILABLE'],
    '#1a8f4a',
    ['==', ['get', 'dynamic_status'], 'CHARGING'],
    '#c47a00',
    ['==', ['get', 'dynamic_status'], 'RESERVED'],
    '#c47a00',
    [
      'any',
      ['==', ['get', 'dynamic_status'], 'OUTOFORDER'],
      ['==', ['get', 'dynamic_status'], 'INOPERATIVE'],
    ],
    '#c0392b',
    colors.point,
  ]
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
      'circle-color': pointColorExpression(theme),
      'circle-radius': [
        'case',
        ['has', 'planned_stop_order'],
        ['interpolate', ['linear'], ['zoom'], 6, 7, 10, 11, 14, 14],
        ['interpolate', ['linear'], ['zoom'], 6, 4, 10, 7, 14, 10],
      ],
      'circle-stroke-width': ['case', ['has', 'planned_stop_order'], 2.5, 1.5],
      'circle-stroke-color': colors.pointStroke,
      'circle-opacity': 0.92,
    },
  })

  map.addLayer({
    id: PLANNED_STOP_LABEL_LAYER_ID,
    type: 'symbol',
    source: STATIONS_SOURCE_ID,
    filter: ['all', ['!', ['has', 'point_count']], ['has', 'planned_stop_order']],
    layout: {
      'text-field': ['to-string', ['get', 'planned_stop_order']],
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 11,
      'text-allow-overlap': true,
    },
    paint: {
      'text-color': '#ffffff',
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
  map.setPaintProperty(POINT_LAYER_ID, 'circle-color', pointColorExpression(theme))
  map.setPaintProperty(POINT_LAYER_ID, 'circle-stroke-color', colors.pointStroke)
  if (map.getLayer(PLANNED_STOP_LABEL_LAYER_ID)) {
    map.setPaintProperty(PLANNED_STOP_LABEL_LAYER_ID, 'text-color', '#ffffff')
  }
}

export function setStationData(map: maplibregl.Map, data: FeatureCollection): void {
  const source = map.getSource(STATIONS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
  }
}

import { navigationPopupHtml } from '../navigation/externalMaps'
import { dynamicStatusClassName, formatDynamicStatusLabel } from '../stations/dynamicDisplay'

export function stationPopupHtml(
  properties: Record<string, unknown>,
  coords?: { lat: number; lon: number },
): string {
  const siteName = String(properties.site_name ?? properties.id ?? 'Estación')
  const operator = properties.operator ? String(properties.operator) : 'Operador desconocido'
  const maxKw = Number(properties.max_power_kw ?? 0)
  const connectors = Number(properties.connector_count ?? 0)
  const connectorSummary =
    properties.connector_summary ? String(properties.connector_summary) : `${maxKw.toFixed(0)} kW`
  const connectorLine =
    connectors > 0
      ? `${connectorSummary} · ${connectors} conector${connectors === 1 ? '' : 'es'}`
      : connectorSummary
  const country = properties.country ? String(properties.country) : ''
  const address = properties.address ? String(properties.address) : ''
  const dynamicStatus = properties.dynamic_status ? String(properties.dynamic_status) : ''
  const dynamicPrice = properties.dynamic_price_eur_kwh
  const chargingClass = properties.charging_classification ? String(properties.charging_classification) : ''
  const socArrival = properties.soc_arrival_pct
  const plannedOrder = properties.planned_stop_order
  const socDeparture = properties.soc_departure_pct
  const chargeMinutes = properties.charge_minutes

  const addressLine = address ? `<p class="station-popup__address">${address}</p>` : ''
  const dynamicLine = formatDynamicLine(dynamicStatus, dynamicPrice)
  const externalLine = formatExternalReviewsLine(properties)
  const chargeLine = formatChargeLine(chargingClass, socArrival, plannedOrder, socDeparture, chargeMinutes)
  const navLine = coords ? navigationPopupHtml(coords.lat, coords.lon) : ''

  return `
    <div class="station-popup">
      <p class="station-popup__title">${escapeHtml(siteName)}</p>
      <p class="station-popup__operator">${escapeHtml(operator)}</p>
      <p class="station-popup__meta">
        <strong>${escapeHtml(connectorLine)}</strong>
        ${country ? ` · ${escapeHtml(country)}` : ''}
      </p>
      ${dynamicLine}
      ${externalLine}
      ${chargeLine}
      ${addressLine}
      ${navLine}
    </div>
  `
}

function formatChargeLine(
  classification: string,
  socArrival: unknown,
  plannedOrder: unknown,
  socDeparture: unknown,
  chargeMinutes: unknown,
): string {
  if (!classification && plannedOrder == null) {
    return ''
  }
  const orderText =
    plannedOrder != null && !Number.isNaN(Number(plannedOrder))
      ? `<strong>Parada ${Number(plannedOrder)}</strong> · `
      : ''
  const socText =
    socArrival !== null && socArrival !== undefined && !Number.isNaN(Number(socArrival))
      ? ` llegada ${Number(socArrival).toFixed(0)} %`
      : ''
  const departureText =
    socDeparture !== null && socDeparture !== undefined && !Number.isNaN(Number(socDeparture))
      ? ` · salida ${Number(socDeparture).toFixed(0)} %`
      : ''
  const chargeText =
    chargeMinutes !== null && chargeMinutes !== undefined && Number(chargeMinutes) > 0
      ? ` · ~${Number(chargeMinutes).toFixed(0)} min carga`
      : ''
  const classText = classification ? escapeHtml(classification) : 'planificada'
  return `<p class="station-popup__charge">${orderText}${classText}${socText}${departureText}${chargeText}</p>`
}

function parseExternalComments(raw: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(raw)) {
    return raw.filter((item) => item && typeof item === 'object') as Array<Record<string, unknown>>
  }
  if (typeof raw === 'string' && raw.trim()) {
    try {
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        return parsed.filter((item) => item && typeof item === 'object') as Array<Record<string, unknown>>
      }
    } catch {
      return []
    }
  }
  return []
}

function formatExternalReviewsLine(properties: Record<string, unknown>): string {
  const ratingAvg = properties.external_rating_avg
  const ratingCount = properties.external_rating_count
  const avg = ratingAvg != null ? Number(ratingAvg) : NaN
  const count = ratingCount != null ? Number(ratingCount) : 0
  const comments = parseExternalComments(properties.external_comments)
  const parts: string[] = []
  if (!Number.isNaN(avg) && count > 0) {
    parts.push(
      `<p class="station-popup__reviews"><strong>${avg.toFixed(1)}/5</strong> · ${count} valoraciones · Open Charge Map</p>`,
    )
  }
  for (const item of comments.slice(0, 2)) {
    const text = item.comment ? String(item.comment) : item.checkin_label ? String(item.checkin_label) : ''
    if (!text) {
      continue
    }
    const rating = item.rating != null ? `${Number(item.rating)}/5 · ` : ''
    parts.push(`<p class="station-popup__review">${escapeHtml(rating + text)}</p>`)
  }
  return parts.join('')
}

function formatDynamicLine(status: string, price: unknown): string {
  if (!status && (price === null || price === undefined || Number.isNaN(Number(price)))) {
    return ''
  }
  const parts: string[] = []
  if (status) {
    parts.push(
      `<span class="station-popup__status ${dynamicStatusClassName(status, 'station-popup')}">${escapeHtml(formatDynamicStatusLabel(status))}</span>`,
    )
  }
  if (price !== null && price !== undefined && !Number.isNaN(Number(price))) {
    parts.push(`<span class="station-popup__price">${Number(price).toFixed(2)} €/kWh sin IVA</span>`)
  }
  return `<p class="station-popup__dynamic">${parts.join(' · ')}</p>`
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}
