import type { ChargingPlanStopResult, StationFeature } from './types'

export function chargingPlanStopToFeature(stop: ChargingPlanStopResult): StationFeature {
  const station = stop.station
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
      address: station.location.address ?? null,
      dynamic_status: station.dynamic_status ?? null,
      dynamic_price_eur_kwh: station.dynamic_price_eur_kwh ?? null,
      dynamic_updated_at: station.dynamic_updated_at ?? null,
      external_rating_avg: station.external_rating_avg ?? null,
      external_rating_count: station.external_rating_count ?? 0,
      external_comments: station.external_comments?.slice(0, 3) ?? [],
      charging_classification: stop.classification,
      soc_arrival_pct: stop.soc_arrival_pct,
    },
  }
}

export function chargingPlanToFeatures(
  stops: ChargingPlanStopResult[],
  originStops: ChargingPlanStopResult[] = [],
): StationFeature[] {
  const seen = new Set<string>()
  const features: StationFeature[] = []
  for (const stop of [...originStops, ...stops]) {
    if (seen.has(stop.station.id)) {
      continue
    }
    seen.add(stop.station.id)
    features.push(chargingPlanStopToFeature(stop))
  }
  return features
}
