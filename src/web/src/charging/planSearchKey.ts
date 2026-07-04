import type { RoutePreference } from '../api/types'
import type { ChargingPreferencesState } from './chargingPreferences'

export type PlanSearchKeyInput = {
  originMode: 'car' | 'gps' | 'simulation'
  origin: { lat: number; lon: number; source?: string }
  dest: { label: string; lat: number; lon: number } | null
  vehicleQuery: {
    soc_percent: number
    usable_capacity_kwh: number
    consumption_wh_per_km: number
    terrain_factor: number
    reserve_soc_percent?: number
    vehicle_preset_id?: string | null
  }
  minKw?: number
  maxKw?: number
  corridorKm: number
  emergencyMode: boolean
  routePreference: RoutePreference
  avoidTolls: boolean
  chargingPreferences: ChargingPreferencesState
}

export function locationSearchKey(point: { lat: number; lon: number; source?: string }): string {
  return `${point.lat.toFixed(3)},${point.lon.toFixed(3)},${point.source ?? 'point'}`
}

export function buildPlanSearchKey(input: PlanSearchKeyInput): string {
  return JSON.stringify({
    originMode: input.originMode,
    origin: locationSearchKey(input.origin),
    dest: input.emergencyMode ? null : input.dest,
    vehicleQuery: input.vehicleQuery,
    minKw: input.minKw,
    maxKw: input.maxKw,
    corridorKm: input.corridorKm,
    emergencyMode: input.emergencyMode,
    routePreference: input.routePreference,
    avoidTolls: input.avoidTolls,
    chargingPreferences: input.chargingPreferences,
  })
}
