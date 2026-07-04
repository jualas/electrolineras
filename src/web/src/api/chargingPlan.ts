import { fetchApi } from './client'
import { chargingPreferencesToQueryParams } from '../charging/chargingPreferences'
import type { ChargingPlanResponse, RoutePreference } from './types'

export type ChargingPlanQuery = {
  originLat: number
  originLon: number
  destLat?: number
  destLon?: number
  socPercent: number
  usableCapacityKwh: number
  consumptionWhPerKm: number
  terrainFactor: number
  reserveSocPercent?: number
  minKw?: number
  maxKw?: number
  corridorKm?: number
  limit?: number
  routePreference?: RoutePreference
  avoidHighways?: boolean
  vehiclePresetId?: string
  preferredOperators?: string[]
  maxPriceEurKwh?: number | null
}

export async function fetchChargingPlan(
  query: ChargingPlanQuery,
  init?: RequestInit,
): Promise<ChargingPlanResponse> {
  const params = new URLSearchParams({
    origin_lat: String(query.originLat),
    origin_lon: String(query.originLon),
    soc_percent: String(query.socPercent),
    usable_capacity_kwh: String(query.usableCapacityKwh),
    consumption_wh_per_km: String(query.consumptionWhPerKm),
    terrain_factor: String(query.terrainFactor),
    include_route: 'true',
  })

  if (query.destLat !== undefined && query.destLon !== undefined) {
    params.set('dest_lat', String(query.destLat))
    params.set('dest_lon', String(query.destLon))
  }
  if (query.reserveSocPercent !== undefined) {
    params.set('reserve_soc_percent', String(query.reserveSocPercent))
  }
  if (query.minKw !== undefined) {
    params.set('min_kw', String(query.minKw))
  }
  if (query.maxKw !== undefined) {
    params.set('max_kw', String(query.maxKw))
  }
  if (query.corridorKm !== undefined) {
    params.set('corridor_km', String(query.corridorKm))
  }
  if (query.limit !== undefined) {
    params.set('limit', String(query.limit))
  }
  if (query.routePreference !== undefined) {
    params.set('route_preference', query.routePreference)
  }
  if (query.avoidHighways) {
    params.set('avoid_highways', 'true')
  }
  if (query.vehiclePresetId) {
    params.set('vehicle_preset_id', query.vehiclePresetId)
  }
  const preferenceParams = chargingPreferencesToQueryParams({
    preferredOperators: query.preferredOperators ?? [],
    maxPriceEurKwh: query.maxPriceEurKwh ?? null,
  })
  for (const [key, value] of Object.entries(preferenceParams)) {
    params.set(key, value)
  }

  return fetchApi<ChargingPlanResponse>(`/api/v1/stations/charging-plan?${params.toString()}`, init)
}

export { stationLabel } from './route'
