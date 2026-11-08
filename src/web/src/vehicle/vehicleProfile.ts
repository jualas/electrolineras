import {
  driverFactor,
  getActiveVehicle,
  type GarageState,
} from './garage'
import { getTerrainFactor, type TerrainFactorId, type VehiclePresetId } from './vehiclePresets'

export { DEFAULT_SOC_PERCENT, SOC_MAX, SOC_MIN } from './garage'

/** Vehículo activo del garaje + estado del viaje, ya resuelto para planificar. */
export type VehicleProfile = {
  vehicleId: string
  name: string
  /** Modelo de catálogo de partida (curva DC en la API); null = vehículo libre. */
  presetId: VehiclePresetId | null
  usableCapacityKwh: number
  peakDcKw: number
  homologatedKwhPer100km: number
  /** Factor personal de conducción (1 = homologado). */
  driverFactor: number
  /** Consumo base de planificación (homologado × factor personal), sin terreno. */
  consumptionWhPerKm: number
  teslaMateLinked: boolean
  socPercent: number
  terrainFactorId: TerrainFactorId
}

export const DEFAULT_RESERVE_SOC_PERCENT = 10
export const CONSUMPTION_MIN_WH_KM = 80
export const CONSUMPTION_MAX_WH_KM = 350

export function resolveVehicleProfile(state: GarageState): VehicleProfile {
  const vehicle = getActiveVehicle(state)
  const factor = driverFactor(state)
  const consumption = Math.min(
    CONSUMPTION_MAX_WH_KM,
    Math.max(CONSUMPTION_MIN_WH_KM, Math.round(vehicle.homologatedKwhPer100km * 10 * factor)),
  )
  return {
    vehicleId: vehicle.id,
    name: vehicle.name,
    presetId: vehicle.basePresetId,
    usableCapacityKwh: vehicle.usableCapacityKwh,
    peakDcKw: vehicle.peakDcKw,
    homologatedKwhPer100km: vehicle.homologatedKwhPer100km,
    driverFactor: factor,
    consumptionWhPerKm: consumption,
    teslaMateLinked: vehicle.teslaMateLinked,
    socPercent: state.socPercent,
    terrainFactorId: state.terrainFactorId,
  }
}

export function effectiveConsumptionWhPerKm(profile: VehicleProfile): number {
  return profile.consumptionWhPerKm * getTerrainFactor(profile.terrainFactorId).factor
}

/** Km con la energía entre el SOC actual y `floorSocPercent` (mismo cálculo que la API). */
function rangeAboveSocKm(profile: VehicleProfile, floorSocPercent: number): number {
  const consumptionKwhPerKm = effectiveConsumptionWhPerKm(profile) / 1000
  if (consumptionKwhPerKm <= 0) {
    return 0
  }
  const usableSoc = Math.max(0, profile.socPercent - floorSocPercent)
  return Math.round((profile.usableCapacityKwh * usableSoc) / 100 / consumptionKwhPerKm)
}

export function availableEnergyKwh(
  profile: VehicleProfile,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  const usableSoc = Math.max(0, profile.socPercent - reserveSocPercent)
  return (profile.usableCapacityKwh * usableSoc) / 100
}

/** Autonomía hasta 0 % con el consumo previsto (equivalente al cuadro del coche). */
export function estimateDisplayedRangeKm(profile: VehicleProfile): number {
  return rangeAboveSocKm(profile, 0)
}

export function estimatePlanningRangeKm(
  profile: VehicleProfile,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  return rangeAboveSocKm(profile, reserveSocPercent)
}

/** Distancia máxima hasta un cargador (llegada ≥ minArrivalSoc %, típ. 5 %). */
export function estimateChargingReachKm(profile: VehicleProfile, minArrivalSoc = 5): number {
  return rangeAboveSocKm(profile, minArrivalSoc)
}

/** Alias de planificación (mapa / API). */
export function estimateRangeKm(
  profile: VehicleProfile,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  return estimatePlanningRangeKm(profile, reserveSocPercent)
}

export function formatVehicleSummary(profile: VehicleProfile): string {
  const terrain = getTerrainFactor(profile.terrainFactorId)
  const displayedKm = estimateDisplayedRangeKm(profile)
  const planningKm = estimatePlanningRangeKm(profile)
  const effectiveWh = Math.round(effectiveConsumptionWhPerKm(profile))
  const terrainNote = terrain.factor === 1 ? '' : ` · ${terrain.label}`
  return `${profile.socPercent} % SOC · ~${displayedKm} km${terrainNote} · plan ~${planningKm} km · ${effectiveWh} Wh/km`
}

/** «15,2 homologado × 1,08 = 16,4 kWh/100 km» */
export function formatConsumptionBreakdown(profile: VehicleProfile): string {
  const fmt = (value: number) => value.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  const base = profile.consumptionWhPerKm / 10
  if (profile.driverFactor === 1) {
    return `${fmt(profile.homologatedKwhPer100km)} kWh/100 km homologado (sin perfil de conducción)`
  }
  return `${fmt(profile.homologatedKwhPer100km)} homologado × ${fmt(profile.driverFactor)} tu conducción = ${fmt(base)} kWh/100 km`
}

export function vehicleProfileToChargingPlanQuery(profile: VehicleProfile): {
  soc_percent: number
  usable_capacity_kwh: number
  consumption_wh_per_km: number
  terrain_factor: number
  reserve_soc_percent: number
  vehicle_preset_id?: string
} {
  const terrain = getTerrainFactor(profile.terrainFactorId)
  return {
    soc_percent: profile.socPercent,
    usable_capacity_kwh: profile.usableCapacityKwh,
    consumption_wh_per_km: profile.consumptionWhPerKm,
    terrain_factor: terrain.factor,
    reserve_soc_percent: DEFAULT_RESERVE_SOC_PERCENT,
    ...(profile.presetId ? { vehicle_preset_id: profile.presetId } : {}),
  }
}
