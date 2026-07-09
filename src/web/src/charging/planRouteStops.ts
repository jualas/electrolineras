import type { ChargingPlanResponse, ChargingPlanStopResult, PlannedRouteStopResult, StationFeature } from '../api/types'
import type { MapCoords, RouteExportSpec } from '../navigation/externalMaps'
import { googleMapsRouteUrl } from '../navigation/externalMaps'
import { chargingPlanStopToFeature, plannedRouteStopToFeature } from '../api/chargingPlanFeature'

const GOOGLE_MAPS_MAX_WAYPOINTS = 8

export type RouteChargingStop = ChargingPlanStopResult | PlannedRouteStopResult

function isPlannedStop(stop: RouteChargingStop): stop is PlannedRouteStopResult {
  return 'order' in stop && typeof stop.order === 'number'
}

/** Plan multi-parada completo (llega al destino con margen razonable). */
export function isChargingPlanComplete(plan: ChargingPlanResponse): boolean {
  const planned = plan.planned_stops ?? []
  if (planned.length === 0) {
    return false
  }
  if (plan.warnings.some((warning) => warning.includes('No hay cargador alcanzable'))) {
    return false
  }
  if (
    plan.projected_soc_at_destination_with_plan != null &&
    plan.projected_soc_at_destination_with_plan < 20
  ) {
    return false
  }
  return true
}

const ORIGIN_CHARGE_SOC_THRESHOLD = 10
const MIN_ORIGIN_SKIP_KM = 40

function minDistanceFromOriginKm(plan: ChargingPlanResponse): number {
  const routeKm =
    plan.route_distance_km ??
    plan.route_fastest_distance_km ??
    plan.route_shortest_distance_km ??
    0
  const avgSpeedKmh =
    routeKm > 0 && plan.route_duration_minutes != null && plan.route_duration_minutes > 0
      ? routeKm / (plan.route_duration_minutes / 60)
      : 90
  const targetLegKm = avgSpeedKmh * 2
  if (plan.vehicle.soc_percent < ORIGIN_CHARGE_SOC_THRESHOLD) {
    return 0
  }
  return Math.max(MIN_ORIGIN_SKIP_KM, targetLegKm)
}

function excludeOriginNearStops(
  stops: ChargingPlanStopResult[],
  plan: ChargingPlanResponse,
): ChargingPlanStopResult[] {
  const minKm = minDistanceFromOriginKm(plan)
  if (minKm <= 0) {
    return stops
  }
  return stops.filter((stop) => stop.route_distance_km >= minKm - 1e-6)
}

function viableCorridorStops(plan: ChargingPlanResponse): ChargingPlanStopResult[] {
  return excludeOriginNearStops(
    plan.stops
      .filter((stop) => stop.classification !== 'unreachable')
      .sort((a, b) => a.route_distance_km - b.route_distance_km),
    plan,
  )
}

function estimateChargingStopCount(plan: ChargingPlanResponse): number {
  const routeKm =
    plan.route_distance_km ??
    plan.route_fastest_distance_km ??
    plan.route_shortest_distance_km ??
    plan.geodesic_distance_km ??
    0
  const avgSpeedKmh =
    routeKm > 0 && plan.route_duration_minutes != null && plan.route_duration_minutes > 0
      ? routeKm / (plan.route_duration_minutes / 60)
      : 90
  const targetLegKm = avgSpeedKmh * 2
  if (routeKm <= targetLegKm + 1) {
    return 0
  }
  return Math.min(GOOGLE_MAPS_MAX_WAYPOINTS, Math.max(1, Math.ceil(routeKm / targetLegKm) - 1))
}

function pickStopsByRouteDistance(
  stops: ChargingPlanStopResult[],
  count: number,
  routeKm: number,
): ChargingPlanStopResult[] {
  if (stops.length === 0 || count <= 0 || routeKm <= 0) {
    return []
  }
  const targets: number[] = []
  for (let index = 0; index < count; index += 1) {
    targets.push(((index + 1) * routeKm) / (count + 1))
  }
  const picked: ChargingPlanStopResult[] = []
  const used = new Set<string>()
  for (const targetKm of targets) {
    const candidate = stops
      .filter((stop) => !used.has(stop.station.id))
      .sort(
        (a, b) =>
          Math.abs(a.route_distance_km - targetKm) - Math.abs(b.route_distance_km - targetKm) ||
          b.station.max_power_kw - a.station.max_power_kw,
      )[0]
    if (candidate) {
      picked.push(candidate)
      used.add(candidate.station.id)
    }
  }
  return picked.sort((a, b) => a.route_distance_km - b.route_distance_km)
}

/** Paradas de carga a mostrar en mapa y exportar (solo planificadas si existen). */
export function routeChargingStops(plan: ChargingPlanResponse): RouteChargingStop[] {
  const planned = plan.planned_stops ?? []
  if (planned.length > 0) {
    const minKm = minDistanceFromOriginKm(plan)
    if (minKm <= 0) {
      return planned
    }
    return planned.filter((stop) => stop.route_distance_km >= minKm - 1e-6)
  }
  if (plan.reachable_without_stop || plan.mode === 'emergency') {
    return []
  }
  const viable = viableCorridorStops(plan)
  if (viable.length === 0) {
    return []
  }
  const routeKm =
    plan.route_distance_km ??
    plan.route_fastest_distance_km ??
    plan.route_shortest_distance_km ??
    0
  const count = estimateChargingStopCount(plan)
  return pickStopsByRouteDistance(viable, count, routeKm)
}

export function routeChargingWaypoints(plan: ChargingPlanResponse): MapCoords[] {
  return routeChargingStops(plan).map((stop) => stop.station.location)
}

export function routeExportSpecFromChargingPlan(plan: ChargingPlanResponse): RouteExportSpec | null {
  if (!plan.destination) {
    return null
  }
  const waypoints = routeChargingWaypoints(plan)
  return {
    origin: plan.origin,
    destination: plan.destination,
    waypoints: waypoints.length > 0 ? waypoints : undefined,
    title: 'Viaje Electrolineras',
  }
}

export function googleMapsRouteUrlFromPlan(plan: ChargingPlanResponse): string | null {
  const spec = routeExportSpecFromChargingPlan(plan)
  if (!spec) {
    return null
  }
  return googleMapsRouteUrl({
    origin: spec.origin,
    destination: spec.destination,
    waypoints: spec.waypoints,
    maxWaypoints: GOOGLE_MAPS_MAX_WAYPOINTS,
  })
}

export function chargingPlanRouteMapFeatures(plan: ChargingPlanResponse): StationFeature[] {
  return routeChargingStops(plan).map((stop, index) => {
    if (isPlannedStop(stop)) {
      return plannedRouteStopToFeature(stop)
    }
    return chargingPlanStopToFeature(stop, { plannedOrder: index + 1 })
  })
}

export function routeMapFitPoints(plan: ChargingPlanResponse): MapCoords[] {
  const charging = routeChargingWaypoints(plan)
  const points: MapCoords[] = [plan.origin, ...charging]
  if (plan.destination) {
    points.push(plan.destination)
  }
  return points
}
