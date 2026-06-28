import type { Station, StationFeature } from './types'
import { summarizeConnectors } from '../stations/connectorDisplay'

export function stationToFeature(station: Station): StationFeature {
  return {
    type: 'Feature',
    id: station.id,
    geometry: {
      type: 'Point',
      coordinates: [station.location.lon, station.location.lat],
    },
    properties: {
      id: station.id,
      source: station.source,
      country: station.country,
      site_name: station.site_name,
      operator: station.operator,
      max_power_kw: station.max_power_kw,
      access: station.access,
      connector_count: station.connectors.length,
      connector_summary: summarizeConnectors(station.connectors),
      address: station.location.address ?? null,
      dynamic_status: station.dynamic_status ?? null,
      dynamic_price_eur_kwh: station.dynamic_price_eur_kwh ?? null,
      dynamic_updated_at: station.dynamic_updated_at ?? null,
      external_rating_avg: station.external_rating_avg ?? null,
      external_rating_count: station.external_rating_count ?? 0,
      external_comments: station.external_comments?.slice(0, 3) ?? [],
      ocm_poi_id: station.ocm_poi_id ?? null,
    },
  }
}
