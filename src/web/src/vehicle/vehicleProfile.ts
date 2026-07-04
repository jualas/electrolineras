import {
  DEFAULT_TERRAIN_FACTOR_ID,
  DEFAULT_VEHICLE_PRESET_ID,
  getTerrainFactor,
  getVehiclePreset,
  type TerrainFactorId,
  type VehiclePresetDefinition,
  type VehiclePresetId,
} from './vehiclePresets'

export type VehicleProfile = {
  presetId: VehiclePresetId
  socPercent: number
  consumptionWhPerKm: number
  terrainFactorId: TerrainFactorId
}

export const SOC_MIN = 5
export const SOC_MAX = 100
export const DEFAULT_SOC_PERCENT = 80
export const DEFAULT_RESERVE_SOC_PERCENT = 10
export const CONSUMPTION_MIN_WH_KM = 80
export const CONSUMPTION_MAX_WH_KM = 350

const STORAGE_KEY = 'electrolineras.vehicleProfile'

export function createDefaultVehicleProfile(): VehicleProfile {
  const preset = getVehiclePreset(DEFAULT_VEHICLE_PRESET_ID)
  return {
    presetId: preset.id,
    socPercent: DEFAULT_SOC_PERCENT,
    consumptionWhPerKm: preset.referenceWhPerKm,
    terrainFactorId: DEFAULT_TERRAIN_FACTOR_ID,
  }
}

function clampSoc(value: number): number {
  return Math.min(SOC_MAX, Math.max(SOC_MIN, Math.round(value)))
}

function clampConsumption(value: number): number {
  return Math.min(CONSUMPTION_MAX_WH_KM, Math.max(CONSUMPTION_MIN_WH_KM, Math.round(value)))
}

export function normalizeVehicleProfile(raw: Partial<VehicleProfile> | null | undefined): VehicleProfile {
  const defaults = createDefaultVehicleProfile()
  if (!raw) {
    return defaults
  }

  const preset = getVehiclePreset(typeof raw.presetId === 'string' ? raw.presetId : defaults.presetId)
  const terrainFactorId =
    raw.terrainFactorId === 'flat' || raw.terrainFactorId === 'rolling' || raw.terrainFactorId === 'mountain'
      ? raw.terrainFactorId
      : defaults.terrainFactorId

  return {
    presetId: preset.id,
    socPercent: clampSoc(typeof raw.socPercent === 'number' ? raw.socPercent : defaults.socPercent),
    consumptionWhPerKm: clampConsumption(
      typeof raw.consumptionWhPerKm === 'number' ? raw.consumptionWhPerKm : preset.referenceWhPerKm,
    ),
    terrainFactorId,
  }
}

export function loadStoredVehicleProfile(): VehicleProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as Partial<VehicleProfile>
    const profile = normalizeVehicleProfile(parsed)
    return migrateLegacyConsumption(profile)
  } catch {
    return null
  }
}

/** Recalibrar consumo guardado cuando coincide con valores antiguos del preset. */
function migrateLegacyConsumption(profile: VehicleProfile): VehicleProfile {
  const preset = getVehiclePreset(profile.presetId)
  const legacyByPreset: Partial<Record<VehiclePresetId, number>> = {
    'tesla-model3-sr-2023': 142,
    'tesla-model-y-lr': 158,
    'vw-id3-pro': 155,
    'hyundai-kona-64': 168,
    'renault-megane-etech': 162,
    'bmw-i4-edrive40': 175,
    'mg4-standard': 160,
    'nissan-leaf-62': 178,
  }
  const legacyWh = legacyByPreset[profile.presetId]
  if (legacyWh != null && profile.consumptionWhPerKm === legacyWh) {
    return { ...profile, consumptionWhPerKm: preset.referenceWhPerKm }
  }
  return profile
}

export function storeVehicleProfile(profile: VehicleProfile): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
}

export function profileFromPreset(presetId: VehiclePresetId, current?: VehicleProfile): VehicleProfile {
  const preset = getVehiclePreset(presetId)
  return normalizeVehicleProfile({
    presetId: preset.id,
    socPercent: current?.socPercent,
    consumptionWhPerKm: preset.referenceWhPerKm,
    terrainFactorId: current?.terrainFactorId,
  })
}

export function effectiveConsumptionWhPerKm(profile: VehicleProfile): number {
  const terrain = getTerrainFactor(profile.terrainFactorId)
  return profile.consumptionWhPerKm * terrain.factor
}

export function availableEnergyKwh(
  profile: VehicleProfile,
  preset: VehiclePresetDefinition,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  const usableSoc = Math.max(0, profile.socPercent - reserveSocPercent)
  return (preset.usableCapacityKwh * usableSoc) / 100
}

/** Autonomía como el cuadro del coche (100 % → ratedRangeKm del preset). */
export function estimateDisplayedRangeKm(
  profile: VehicleProfile,
  preset?: VehiclePresetDefinition,
): number {
  const resolvedPreset = preset ?? getVehiclePreset(profile.presetId)
  const terrain = getTerrainFactor(profile.terrainFactorId)
  return Math.round((resolvedPreset.ratedRangeKm * profile.socPercent) / 100 / terrain.factor)
}

export function estimatePlanningRangeKm(
  profile: VehicleProfile,
  preset?: VehiclePresetDefinition,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  const resolvedPreset = preset ?? getVehiclePreset(profile.presetId)
  const terrain = getTerrainFactor(profile.terrainFactorId)
  const usableSoc = Math.max(0, profile.socPercent - reserveSocPercent)
  return Math.round((resolvedPreset.ratedRangeKm * usableSoc) / 100 / terrain.factor)
}

/** Distancia máxima hasta un cargador (llegada ≥ minArrivalSoc %, típ. 5 %). */
export function estimateChargingReachKm(
  profile: VehicleProfile,
  preset?: VehiclePresetDefinition,
  minArrivalSoc = 5,
): number {
  const resolvedPreset = preset ?? getVehiclePreset(profile.presetId)
  const terrain = getTerrainFactor(profile.terrainFactorId)
  const usableSoc = Math.max(0, profile.socPercent - minArrivalSoc)
  return Math.round((resolvedPreset.ratedRangeKm * usableSoc) / 100 / terrain.factor)
}

/** Alias de planificación (mapa / API). */
export function estimateRangeKm(
  profile: VehicleProfile,
  preset?: VehiclePresetDefinition,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  return estimatePlanningRangeKm(profile, preset, reserveSocPercent)
}

export function formatVehicleSummary(profile: VehicleProfile): string {
  const preset = getVehiclePreset(profile.presetId)
  const terrain = getTerrainFactor(profile.terrainFactorId)
  const displayedKm = estimateDisplayedRangeKm(profile, preset)
  const planningKm = estimatePlanningRangeKm(profile, preset)
  const effectiveWh = Math.round(effectiveConsumptionWhPerKm(profile))
  const terrainNote = terrain.factor === 1 ? '' : ` · ${terrain.label}`
  return `${profile.socPercent} % SOC · ~${displayedKm} km${terrainNote} · plan ~${planningKm} km · ${effectiveWh} Wh/km`
}

export function vehicleProfileToChargingPlanQuery(profile: VehicleProfile): {
  soc_percent: number
  usable_capacity_kwh: number
  consumption_wh_per_km: number
  terrain_factor: number
  reserve_soc_percent: number
  vehicle_preset_id: string
} {
  const preset = getVehiclePreset(profile.presetId)
  const terrain = getTerrainFactor(profile.terrainFactorId)
  return {
    soc_percent: profile.socPercent,
    usable_capacity_kwh: preset.usableCapacityKwh,
    consumption_wh_per_km: profile.consumptionWhPerKm,
    terrain_factor: terrain.factor,
    reserve_soc_percent: DEFAULT_RESERVE_SOC_PERCENT,
    vehicle_preset_id: preset.id,
  }
}
