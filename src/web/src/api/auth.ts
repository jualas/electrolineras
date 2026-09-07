import type { AuthConfigResponse, AuthSessionResponse } from '../api/types'

import { fetchApi } from './client'
import { chargingPreferencesToQueryParams } from '../charging/chargingPreferences'

export async function fetchAuthConfig(): Promise<AuthConfigResponse> {
  return fetchApi<AuthConfigResponse>('/api/v1/auth/config')
}

export async function fetchAuthSession(): Promise<AuthSessionResponse> {
  return fetchApi<AuthSessionResponse>('/api/v1/auth/session')
}

export async function loginWithTotp(username: string, totpCode: string): Promise<void> {
  await fetchApi('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, totp_code: totpCode }),
  })
}

export async function logoutSession(): Promise<void> {
  await fetchApi('/api/v1/auth/logout', { method: 'POST' })
}

export async function fetchVehicleState(): Promise<import('../api/types').VehicleTelemetryResult> {
  return fetchApi('/api/v1/private/vehicle/state')
}

export async function fetchTripAdviceFromCar(params: {
  destLat: number
  destLon: number
  viaPoints?: Array<{ lat: number; lon: number }>
  terrainFactor?: number
  reserveSocPercent?: number
  localMobilityKm?: number
  includeRoute?: boolean
  routePreference?: import('./types').RoutePreference
  avoidHighways?: boolean
  departureSocPercent?: number
  preferredOperators?: string[]
  maxPriceEurKwh?: number | null
  maxChargePowerKw?: number
  minKw?: number
  minDestinationSocPct?: number
  minStopArrivalSocPct?: number
  maxChargeSocPct?: number
  excludeSlowChargers?: boolean
  consumptionKwhPer100km?: number | null
  vehiclePresetId?: string
  usableCapacityKwh?: number
}): Promise<import('../api/types').TripAdviceResponse> {
  const query = new URLSearchParams({
    dest_lat: String(params.destLat),
    dest_lon: String(params.destLon),
  })
  for (const point of params.viaPoints ?? []) {
    query.append('via_lat', String(point.lat))
    query.append('via_lon', String(point.lon))
  }
  if (params.terrainFactor != null) {
    query.set('terrain_factor', String(params.terrainFactor))
  }
  if (params.reserveSocPercent != null) {
    query.set('reserve_soc_percent', String(params.reserveSocPercent))
  }
  if (params.localMobilityKm != null) {
    query.set('local_mobility_km', String(params.localMobilityKm))
  }
  if (params.includeRoute) {
    query.set('include_route', 'true')
  }
  if (params.routePreference) {
    query.set('route_preference', params.routePreference)
  }
  if (params.avoidHighways !== undefined) {
    query.set('avoid_highways', params.avoidHighways ? 'true' : 'false')
  }
  if (params.departureSocPercent != null) {
    query.set('departure_soc_percent', String(params.departureSocPercent))
  }
  for (const [key, value] of Object.entries(
    chargingPreferencesToQueryParams({
      preferredOperators: params.preferredOperators ?? [],
      maxPriceEurKwh: params.maxPriceEurKwh ?? null,
    }),
  )) {
    query.set(key, value)
  }
  appendRevePlanningParams(query, params)
  return fetchApi(`/api/v1/private/trip-advice-from-car?${query}`)
}

function appendRevePlanningParams(
  query: URLSearchParams,
  params: {
    maxChargePowerKw?: number
    minKw?: number
    minDestinationSocPct?: number
    minStopArrivalSocPct?: number
    maxChargeSocPct?: number
    excludeSlowChargers?: boolean
    consumptionKwhPer100km?: number | null
    vehiclePresetId?: string
    usableCapacityKwh?: number
  },
): void {
  if (params.maxChargePowerKw != null) {
    query.set('max_charge_power_kw', String(params.maxChargePowerKw))
  }
  if (params.minKw != null) {
    query.set('min_kw', String(params.minKw))
  }
  if (params.minDestinationSocPct != null) {
    query.set('min_destination_soc_pct', String(params.minDestinationSocPct))
  }
  if (params.minStopArrivalSocPct != null) {
    query.set('min_stop_arrival_soc_pct', String(params.minStopArrivalSocPct))
  }
  if (params.maxChargeSocPct != null) {
    query.set('max_charge_soc_pct', String(params.maxChargeSocPct))
  }
  if (params.excludeSlowChargers) {
    query.set('exclude_slow_chargers', 'true')
  }
  if (params.consumptionKwhPer100km != null) {
    query.set('consumption_kwh_per_100km', String(params.consumptionKwhPer100km))
  }
  if (params.vehiclePresetId) {
    query.set('vehicle_preset_id', params.vehiclePresetId)
  }
  if (params.usableCapacityKwh != null) {
    query.set('usable_capacity_kwh', String(params.usableCapacityKwh))
  }
}

export async function fetchTripGuideFromCar(params: {
  destLat: number
  destLon: number
  destLabel?: string
  viaPoints?: Array<{ lat: number; lon: number }>
  terrainFactor?: number
  reserveSocPercent?: number
  localMobilityKm?: number
  includeRoute?: boolean
  culturalPoi?: boolean
  invokeDify?: boolean
  userNote?: string
  routePreference?: import('./types').RoutePreference
  avoidHighways?: boolean
  departureSocPercent?: number
  preferredOperators?: string[]
  maxPriceEurKwh?: number | null
  maxChargePowerKw?: number
  minKw?: number
  minDestinationSocPct?: number
  minStopArrivalSocPct?: number
  maxChargeSocPct?: number
  excludeSlowChargers?: boolean
  consumptionKwhPer100km?: number | null
  vehiclePresetId?: string
  usableCapacityKwh?: number
}): Promise<import('../api/types').TripGuideResponse> {
  const query = new URLSearchParams({
    dest_lat: String(params.destLat),
    dest_lon: String(params.destLon),
  })
  for (const point of params.viaPoints ?? []) {
    query.append('via_lat', String(point.lat))
    query.append('via_lon', String(point.lon))
  }
  if (params.destLabel) {
    query.set('dest_label', params.destLabel)
  }
  if (params.terrainFactor != null) {
    query.set('terrain_factor', String(params.terrainFactor))
  }
  if (params.reserveSocPercent != null) {
    query.set('reserve_soc_percent', String(params.reserveSocPercent))
  }
  if (params.localMobilityKm != null) {
    query.set('local_mobility_km', String(params.localMobilityKm))
  }
  if (params.includeRoute) {
    query.set('include_route', 'true')
  }
  if (params.culturalPoi === false) {
    query.set('cultural_poi', 'false')
  }
  if (params.invokeDify === false) {
    query.set('invoke_dify', 'false')
  }
  if (params.userNote) {
    query.set('user_note', params.userNote)
  }
  if (params.routePreference) {
    query.set('route_preference', params.routePreference)
  }
  if (params.avoidHighways !== undefined) {
    query.set('avoid_highways', params.avoidHighways ? 'true' : 'false')
  }
  if (params.departureSocPercent != null) {
    query.set('departure_soc_percent', String(params.departureSocPercent))
  }
  for (const [key, value] of Object.entries(
    chargingPreferencesToQueryParams({
      preferredOperators: params.preferredOperators ?? [],
      maxPriceEurKwh: params.maxPriceEurKwh ?? null,
    }),
  )) {
    query.set(key, value)
  }
  appendRevePlanningParams(query, params)
  return fetchApi(`/api/v1/private/trip-guide-from-car?${query}`)
}

export async function fetchTripChat(params: {
  message: string
  history?: import('./types').TripChatMessage[]
  planSnapshot?: Record<string, unknown> | null
  allowLlm?: boolean
}): Promise<import('./types').TripChatResponse> {
  return fetchApi('/api/v1/private/trip-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: params.message,
      history: params.history ?? [],
      plan_snapshot: params.planSnapshot ?? null,
      allow_llm: params.allowLlm !== false,
    }),
  })
}
