import type { ExternalUserComment } from '../api/types'
import { parseExternalComments } from './stationLayers'

export type TappedStationInfo = {
  id: string
  name: string
  operator: string | null
  connectorSummary: string
  lat: number
  lon: number
  dynamicStatus: string | null
  dynamicPriceEurKwh: number | null
  ratingAvg: number | null
  ratingCount: number | null
  comments: ExternalUserComment[]
  address: string | null
}

function toNumberOrNull(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null
  }
  const num = Number(value)
  return Number.isNaN(num) ? null : num
}

export function stationTapInfoFromFeature(
  properties: Record<string, unknown>,
  coords: { lat: number; lon: number },
): TappedStationInfo {
  const maxKw = Number(properties.max_power_kw ?? 0)
  const connectorSummary = properties.connector_summary
    ? String(properties.connector_summary)
    : `${maxKw.toFixed(0)} kW`

  return {
    id: String(properties.id ?? ''),
    name: String(properties.site_name ?? properties.id ?? 'Estación'),
    operator: properties.operator ? String(properties.operator) : null,
    connectorSummary,
    lat: coords.lat,
    lon: coords.lon,
    dynamicStatus: properties.dynamic_status ? String(properties.dynamic_status) : null,
    dynamicPriceEurKwh: toNumberOrNull(properties.dynamic_price_eur_kwh),
    ratingAvg: toNumberOrNull(properties.external_rating_avg),
    ratingCount: toNumberOrNull(properties.external_rating_count),
    comments: parseExternalComments(properties.external_comments) as ExternalUserComment[],
    address: properties.address ? String(properties.address) : null,
  }
}
