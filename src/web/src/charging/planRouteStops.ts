import type { ChargingPlanResponse, ChargingPlanStopResult, PlannedRouteStopResult, StationFeature } from '../api/types'
import type { MapCoords, RouteExportSpec } from '../navigation/externalMaps'
import { googleMapsRouteUrl } from '../navigation/externalMaps'
import { chargingPlanStopToFeature, plannedRouteStopToFeature } from '../api/chargingPlanFeature'
import { DEFAULT_REVE_PLANNING } from '../search/RevePlanningFields'

const GOOGLE_MAPS_MAX_WAYPOINTS = 8

export type RouteChargingStop = ChargingPlanStopResult | PlannedRouteStopResult

function isPlannedStop(stop: RouteChargingStop): stop is PlannedRouteStopResult {
  return 'order' in stop && typeof stop.order === 'number'
}

/** Distancia geodésica aproximada en km (para distancia a la siguiente parada). */
export function haversineKm(a: MapCoords, b: MapCoords): number {
  const earthRadiusKm = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLon = ((b.lon - a.lon) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * earthRadiusKm * Math.asin(Math.sqrt(h))
}

export function chargingStopAtLeg(
  plan: ChargingPlanResponse,
  legIndex: number,
): RouteChargingStop | null {
  const stops = routeChargingStops(plan)
  if (legIndex < 0 || legIndex >= stops.length) {
    return null
  }
  return stops[legIndex]
}

export function routeExportSpecForNextStop(
  plan: ChargingPlanResponse,
  legIndex: number,
): RouteExportSpec | null {
  const stop = chargingStopAtLeg(plan, legIndex)
  if (!stop) {
    return null
  }
  const order = isPlannedStop(stop) ? stop.order : legIndex + 1
  const siteName = stop.station.site_name?.trim() || stop.station.operator || 'Cargador'
  return {
    origin: plan.origin,
    destination: stop.station.location,
    title: `Parada ${order} · ${siteName}`,
  }
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
  // El backend planifica para llegar con min_destination_soc_pct (10 % por defecto,
  // ver DEFAULT_REVE_PLANNING); comprobar contra un umbral más alto aquí marcaba como
  // "incompleto" planes que ya cumplían el objetivo real del optimizador.
  if (
    plan.projected_soc_at_destination_with_plan != null &&
    plan.projected_soc_at_destination_with_plan < DEFAULT_REVE_PLANNING.minDestinationSocPct
  ) {
    return false
  }
  return true
}

const ORIGIN_CHARGE_SOC_THRESHOLD = 10
/** Fracción del alcance donde preferimos paradas (alineado con REACH_STOP_TARGET_FRACTION backend). */
const REACH_STOP_FRACTION = 0.92

function minDistanceFromOriginKm(plan: ChargingPlanResponse): number {
  // Solo autonomía: sin exclusión por ~2 h de conducción.
  if (plan.vehicle.soc_percent <= ORIGIN_CHARGE_SOC_THRESHOLD) {
    return 0
  }
  return 0
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
  const rangeKm = plan.range_km ?? plan.charging_reach_km ?? 0
  if (routeKm <= 0 || rangeKm <= 0 || routeKm <= rangeKm + 1) {
    return 0
  }
  return Math.min(GOOGLE_MAPS_MAX_WAYPOINTS, Math.max(1, Math.ceil(routeKm / rangeKm) - 1))
}

function pickStopsByRouteDistance(
  stops: ChargingPlanStopResult[],
  count: number,
  routeKm: number,
  reachKm?: number,
): ChargingPlanStopResult[] {
  if (stops.length === 0 || count <= 0 || routeKm <= 0) {
    return []
  }
  const step = reachKm != null && reachKm > 0 ? reachKm * REACH_STOP_FRACTION : routeKm / (count + 1)
  const targets: number[] = []
  for (let index = 0; index < count; index += 1) {
    targets.push(Math.min(routeKm * 0.95, (index + 1) * step))
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
    // El backend ya aplicó exclusión de origen / DGT. Filtrar aquí ocultaba la 1.ª
    // parada (p. ej. Hellín ~128 km) y dejaba solo la 2.ª con un `leg_distance_km`
    // relativo a la oculta — el timeline parecía «174 km desde el coche al 9 %».
    return planned
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
  const picked = pickStopsByRouteDistance(
    viable,
    count,
    routeKm,
    plan.charging_reach_km ?? plan.range_km ?? undefined,
  )
  if (picked.length > 0) {
    return picked
  }
  return viable.slice(0, Math.max(count, 3))
}

export function routeChargingWaypoints(plan: ChargingPlanResponse): MapCoords[] {
  return routeChargingStops(plan).map((stop) => stop.station.location)
}

export function routeExportSpecFromChargingPlan(plan: ChargingPlanResponse): RouteExportSpec | null {
  if (!plan.destination) {
    return null
  }
  const chargingStops = routeChargingStops(plan)
  const waypoints = chargingStops.map((stop) => stop.station.location)
  const stopCount = waypoints.length
  return {
    origin: plan.origin,
    destination: plan.destination,
    waypoints: stopCount > 0 ? waypoints : undefined,
    title:
      stopCount > 0
        ? `Viaje Electrolineras · ${stopCount} parada${stopCount === 1 ? '' : 's'} de carga`
        : 'Viaje Electrolineras',
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
