import type { ChargingPlanStopResult, PlannedRouteStopResult, StationFeature } from './types'

export function chargingPlanStopToFeature(
  stop: ChargingPlanStopResult,
  options?: { plannedOrder?: number; socDeparturePct?: number; chargeMinutes?: number },
): StationFeature {
  const station = stop.station
  const properties: StationFeature['properties'] = {
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
    soc_departure_pct: options?.socDeparturePct ?? null,
    charge_minutes: options?.chargeMinutes ?? null,
  }
  if (options?.plannedOrder != null) {
    properties.planned_stop_order = options.plannedOrder
  }

  return {
    type: 'Feature',
    id: options?.plannedOrder != null ? `planned-${options.plannedOrder}-${station.id}` : station.id,
    geometry: {
      type: 'Point',
      coordinates: [station.location.lon, station.location.lat],
    },
    properties,
  }
}

export function plannedRouteStopToFeature(stop: PlannedRouteStopResult): StationFeature {
  return chargingPlanStopToFeature(stop, {
    plannedOrder: stop.order,
    socDeparturePct: stop.soc_departure_pct,
    chargeMinutes: stop.charge_minutes,
  })
}

export function chargingPlanToFeatures(
  stops: ChargingPlanStopResult[],
  originStops: ChargingPlanStopResult[] = [],
  plannedStops: PlannedRouteStopResult[] = [],
): StationFeature[] {
  const seen = new Set<string>()
  const features: StationFeature[] = []

  for (const stop of plannedStops) {
    seen.add(stop.station.id)
    features.push(plannedRouteStopToFeature(stop))
  }

  for (const stop of [...originStops, ...stops]) {
    if (seen.has(stop.station.id)) {
      continue
    }
    seen.add(stop.station.id)
    features.push(chargingPlanStopToFeature(stop))
  }
  return features
}
