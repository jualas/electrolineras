import type { AlongRouteResponse, ChargingPlanResponse, RoutePreference } from '../api/types'
import { activeRouteGeometry, routeVariantGeometriesFromResponse } from '../map/routeComparison'

export function hasCachedChargingPlanVariant(
  cached: ChargingPlanResponse,
  preference: RoutePreference,
): boolean {
  if (cached.route_variant_plans?.[preference]) {
    return true
  }
  return cached.route_preference === preference
}

export function hasCachedAlongRouteVariant(
  cached: AlongRouteResponse,
  preference: RoutePreference,
): boolean {
  if (cached.route_variant_results?.[preference]) {
    return true
  }
  return cached.route_preference === preference
}

export function chargingPlanWithPreference(
  cached: ChargingPlanResponse,
  preference: RoutePreference,
): ChargingPlanResponse | null {
  if (cached.mode !== 'route') {
    return cached.route_preference === preference || !cached.route_preference ? cached : null
  }
  const snapshot = cached.route_variant_plans?.[preference]
  if (!snapshot) {
    return cached.route_preference === preference ? cached : null
  }
  const routeGeometry = activeRouteGeometry(
    preference,
    routeVariantGeometriesFromResponse(cached),
    cached.route_geometry,
  )
  return {
    ...cached,
    route_preference: preference,
    route_distance_km: snapshot.route_distance_km,
    route_duration_minutes: snapshot.route_duration_minutes,
    route_geometry: routeGeometry,
    soc_at_destination_pct: snapshot.soc_at_destination_pct,
    reachable_without_stop: snapshot.reachable_without_stop,
    stops: snapshot.stops,
    origin_stops: snapshot.origin_stops,
    planned_stops: snapshot.planned_stops,
    projected_soc_at_destination_with_plan: snapshot.projected_soc_at_destination_with_plan,
    route_trip_summary: snapshot.route_trip_summary,
    strategies: snapshot.strategies,
    warnings: snapshot.warnings,
    destination_stay: snapshot.destination_stay,
    candidates_in_bbox: snapshot.candidates_in_bbox,
  }
}

export function alongRouteWithPreference(
  cached: AlongRouteResponse,
  preference: RoutePreference,
): AlongRouteResponse | null {
  const snapshot = cached.route_variant_results?.[preference]
  if (!snapshot) {
    return cached.route_preference === preference ? cached : null
  }
  const routeGeometry = activeRouteGeometry(
    preference,
    routeVariantGeometriesFromResponse(cached),
    cached.route_geometry,
  )
  return {
    ...cached,
    route_preference: preference,
    route_distance_km: snapshot.route_distance_km,
    route_duration_minutes: snapshot.route_duration_minutes,
    route_geometry: routeGeometry,
    results: snapshot.results,
    candidates_in_bbox: snapshot.candidates_in_bbox,
  }
}
