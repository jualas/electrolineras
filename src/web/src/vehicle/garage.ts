/**
 * Garaje: varios vehículos + perfil de conducción del usuario.
 *
 * - Cada vehículo guarda sus datos técnicos (batería útil, consumo homologado, pico DC).
 * - SOC y terreno son del viaje, no del coche: se conservan al cambiar de vehículo.
 * - Perfil de conducción: consumo real medido en un vehículo de referencia ÷ su homologado.
 *   Ese factor personal se aplica a cualquier vehículo del garaje (p. ej. al valorar un coche
 *   nuevo). Mientras ambos homologados salgan de la misma fuente, las pérdidas de carga que
 *   incluye la cifra WLTP se compensan dentro del factor.
 */
import {
  DEFAULT_TERRAIN_FACTOR_ID,
  DEFAULT_VEHICLE_PRESET_ID,
  getTerrainFactor,
  VEHICLE_PRESETS,
  type TerrainFactorId,
  type VehiclePresetId,
} from './vehiclePresets'

export type GarageVehicle = {
  id: string
  name: string
  /** Modelo del catálogo del que parte (curva DC en la API); null = vehículo libre. */
  basePresetId: VehiclePresetId | null
  usableCapacityKwh: number
  /** Consumo homologado (kWh/100 km), p. ej. el WLTP de la ficha técnica. */
  homologatedKwhPer100km: number
  peakDcKw: number
  /** Solo este vehículo usa SOC/posición/consumo de TeslaMate. */
  teslaMateLinked: boolean
}

export type DriverProfile = {
  referenceVehicleId: string
  /** Consumo real medido con el vehículo de referencia (kWh/100 km). */
  measuredKwhPer100km: number
}

export type GarageState = {
  vehicles: GarageVehicle[]
  activeVehicleId: string
  driver: DriverProfile | null
  socPercent: number
  terrainFactorId: TerrainFactorId
}

export type GarageVehicleDraft = Omit<GarageVehicle, 'id'>

export const SOC_MIN = 5
export const SOC_MAX = 100
export const DEFAULT_SOC_PERCENT = 100
export const CAPACITY_MIN_KWH = 10
export const CAPACITY_MAX_KWH = 200
export const HOMOLOGATED_MIN_KWH_100 = 8
export const HOMOLOGATED_MAX_KWH_100 = 40
export const PEAK_DC_MIN_KW = 20
export const PEAK_DC_MAX_KW = 350
export const DRIVER_FACTOR_MIN = 0.6
export const DRIVER_FACTOR_MAX = 1.6
export const VEHICLE_NAME_MAX = 40
export const MAX_GARAGE_VEHICLES = 12

export const GARAGE_STORAGE_KEY = 'electrolineras.garage.v1'
export const LEGACY_PROFILE_STORAGE_KEY = 'electrolineras.vehicleProfile'

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function round1(value: number): number {
  return Math.round(value * 10) / 10
}

function finiteOr(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function newVehicleId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return `v-${crypto.randomUUID()}`
    }
  } catch {
    // sin crypto (contexto no seguro): fallback
  }
  return `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function findPreset(presetId: unknown) {
  return typeof presetId === 'string' ? VEHICLE_PRESETS.find((item) => item.id === presetId) ?? null : null
}

/** Datos de partida de un modelo del catálogo (homologado ≈ batería útil ÷ autonomía de referencia). */
export function draftFromPreset(presetId: VehiclePresetId): GarageVehicleDraft {
  const preset = findPreset(presetId) ?? VEHICLE_PRESETS[0]
  return {
    name: preset.label,
    basePresetId: preset.id,
    usableCapacityKwh: preset.usableCapacityKwh,
    homologatedKwhPer100km: round1(preset.referenceWhPerKm / 10),
    peakDcKw: preset.peakDcKw,
    teslaMateLinked: preset.brand === 'Tesla',
  }
}

/** Consumo (kWh/100 km) equivalente a una autonomía homologada con esa batería. */
export function homologatedFromRange(usableCapacityKwh: number, rangeKm: number): number | null {
  if (!(usableCapacityKwh > 0) || !(rangeKm > 0)) {
    return null
  }
  return round1((usableCapacityKwh * 100) / rangeKm)
}

export function normalizeVehicle(raw: Partial<GarageVehicle> | null | undefined, id?: string): GarageVehicle {
  const base = draftFromPreset(findPreset(raw?.basePresetId)?.id ?? DEFAULT_VEHICLE_PRESET_ID)
  const name = typeof raw?.name === 'string' ? raw.name.trim().slice(0, VEHICLE_NAME_MAX) : ''
  return {
    id: typeof raw?.id === 'string' && raw.id ? raw.id : (id ?? newVehicleId()),
    name: name || 'Mi coche',
    basePresetId: findPreset(raw?.basePresetId)?.id ?? null,
    usableCapacityKwh: round1(
      clamp(finiteOr(raw?.usableCapacityKwh, base.usableCapacityKwh), CAPACITY_MIN_KWH, CAPACITY_MAX_KWH),
    ),
    homologatedKwhPer100km: round1(
      clamp(
        finiteOr(raw?.homologatedKwhPer100km, base.homologatedKwhPer100km),
        HOMOLOGATED_MIN_KWH_100,
        HOMOLOGATED_MAX_KWH_100,
      ),
    ),
    peakDcKw: Math.round(clamp(finiteOr(raw?.peakDcKw, base.peakDcKw), PEAK_DC_MIN_KW, PEAK_DC_MAX_KW)),
    teslaMateLinked: raw?.teslaMateLinked === true,
  }
}

function normalizeTerrain(value: unknown): TerrainFactorId {
  return value === 'flat' || value === 'rolling' || value === 'mountain' ? value : DEFAULT_TERRAIN_FACTOR_ID
}

function normalizeSoc(value: unknown): number {
  return Math.round(clamp(finiteOr(value, DEFAULT_SOC_PERCENT), SOC_MIN, SOC_MAX))
}

function normalizeDriver(raw: unknown, vehicles: GarageVehicle[]): DriverProfile | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const candidate = raw as Partial<DriverProfile>
  if (!vehicles.some((item) => item.id === candidate.referenceVehicleId)) {
    return null
  }
  const measured = finiteOr(candidate.measuredKwhPer100km, Number.NaN)
  if (!Number.isFinite(measured) || measured <= 0) {
    return null
  }
  return {
    referenceVehicleId: candidate.referenceVehicleId as string,
    measuredKwhPer100km: round1(clamp(measured, HOMOLOGATED_MIN_KWH_100, HOMOLOGATED_MAX_KWH_100)),
  }
}

export function createDefaultGarage(): GarageState {
  const vehicle = normalizeVehicle({ ...draftFromPreset(DEFAULT_VEHICLE_PRESET_ID) })
  return {
    vehicles: [vehicle],
    activeVehicleId: vehicle.id,
    driver: null,
    socPercent: DEFAULT_SOC_PERCENT,
    terrainFactorId: DEFAULT_TERRAIN_FACTOR_ID,
  }
}

export function normalizeGarage(raw: unknown): GarageState {
  if (!raw || typeof raw !== 'object') {
    return createDefaultGarage()
  }
  const candidate = raw as Partial<GarageState>
  const seen = new Set<string>()
  const vehicles = (Array.isArray(candidate.vehicles) ? candidate.vehicles : [])
    .slice(0, MAX_GARAGE_VEHICLES)
    .map((item) => normalizeVehicle(item as Partial<GarageVehicle>))
    .filter((item) => {
      if (seen.has(item.id)) return false
      seen.add(item.id)
      return true
    })
  if (vehicles.length === 0) {
    return createDefaultGarage()
  }
  const activeVehicleId = vehicles.some((item) => item.id === candidate.activeVehicleId)
    ? (candidate.activeVehicleId as string)
    : vehicles[0].id
  return {
    vehicles,
    activeVehicleId,
    driver: normalizeDriver(candidate.driver, vehicles),
    socPercent: normalizeSoc(candidate.socPercent),
    terrainFactorId: normalizeTerrain(candidate.terrainFactorId),
  }
}

/** Valores de consumo de presets antiguos (antes de recalibrar el catálogo). */
const LEGACY_PRESET_WH: Record<string, number> = {
  'tesla-model3-sr-2023': 142,
  'tesla-model-y-lr': 158,
  'vw-id3-pro': 155,
  'hyundai-kona-64': 168,
  'renault-megane-etech': 162,
  'bmw-i4-edrive40': 175,
  'mg4-standard': 160,
  'nissan-leaf-62': 178,
}

/**
 * Perfil único antiguo → garaje con un vehículo. Si el usuario había ajustado el consumo,
 * se conserva como perfil de conducción (mismo consumo efectivo que antes).
 */
export function migrateLegacyProfile(raw: unknown): GarageState {
  const legacy = (raw && typeof raw === 'object' ? raw : {}) as {
    presetId?: unknown
    socPercent?: unknown
    consumptionWhPerKm?: unknown
    terrainFactorId?: unknown
  }
  const preset = findPreset(legacy.presetId) ?? findPreset(DEFAULT_VEHICLE_PRESET_ID) ?? VEHICLE_PRESETS[0]
  const vehicle = normalizeVehicle({ ...draftFromPreset(preset.id) })
  let driver: DriverProfile | null = null
  const legacyWh = finiteOr(legacy.consumptionWhPerKm, Number.NaN)
  if (
    Number.isFinite(legacyWh) &&
    legacyWh > 0 &&
    legacyWh !== LEGACY_PRESET_WH[preset.id] &&
    Math.round(legacyWh) !== preset.referenceWhPerKm
  ) {
    driver = { referenceVehicleId: vehicle.id, measuredKwhPer100km: legacyWh / 10 }
  }
  return normalizeGarage({
    vehicles: [vehicle],
    activeVehicleId: vehicle.id,
    driver,
    socPercent: legacy.socPercent,
    terrainFactorId: legacy.terrainFactorId,
  })
}

export function loadStoredGarage(): GarageState {
  try {
    const raw = localStorage.getItem(GARAGE_STORAGE_KEY)
    if (raw) {
      return normalizeGarage(JSON.parse(raw))
    }
    const legacy = localStorage.getItem(LEGACY_PROFILE_STORAGE_KEY)
    if (legacy) {
      return migrateLegacyProfile(JSON.parse(legacy))
    }
  } catch {
    // almacenamiento bloqueado o JSON corrupto: garaje por defecto
  }
  return createDefaultGarage()
}

export function storeGarage(state: GarageState): void {
  try {
    localStorage.setItem(GARAGE_STORAGE_KEY, JSON.stringify(state))
  } catch {
    // sin almacenamiento (modo privado): el garaje vive solo en memoria
  }
}

export function getActiveVehicle(state: GarageState): GarageVehicle {
  return state.vehicles.find((item) => item.id === state.activeVehicleId) ?? state.vehicles[0]
}

/** Factor personal = consumo real ÷ homologado del vehículo de referencia (1 sin perfil). */
export function driverFactor(state: Pick<GarageState, 'vehicles' | 'driver'>): number {
  const driver = state.driver
  if (!driver) {
    return 1
  }
  const reference = state.vehicles.find((item) => item.id === driver.referenceVehicleId)
  if (!reference || reference.homologatedKwhPer100km <= 0) {
    return 1
  }
  const factor = driver.measuredKwhPer100km / reference.homologatedKwhPer100km
  return Math.round(clamp(factor, DRIVER_FACTOR_MIN, DRIVER_FACTOR_MAX) * 100) / 100
}

/** Consumo previsto para un vehículo (kWh/100 km) con el perfil de conducción y el terreno. */
export function predictedKwhPer100km(
  state: Pick<GarageState, 'vehicles' | 'driver'>,
  vehicle: GarageVehicle,
  terrainFactorId: TerrainFactorId = 'flat',
): number {
  return round1(vehicle.homologatedKwhPer100km * driverFactor(state) * getTerrainFactor(terrainFactorId).factor)
}

export function addVehicle(state: GarageState, draft: GarageVehicleDraft): GarageState {
  if (state.vehicles.length >= MAX_GARAGE_VEHICLES) {
    return state
  }
  const vehicle = normalizeVehicle({ ...draft })
  return withTeslaMateLink(
    { ...state, vehicles: [...state.vehicles, vehicle], activeVehicleId: vehicle.id },
    vehicle,
  )
}

export function updateVehicle(state: GarageState, id: string, draft: GarageVehicleDraft): GarageState {
  if (!state.vehicles.some((item) => item.id === id)) {
    return state
  }
  const vehicle = normalizeVehicle({ ...draft, id })
  return withTeslaMateLink(
    { ...state, vehicles: state.vehicles.map((item) => (item.id === id ? vehicle : item)) },
    vehicle,
  )
}

/** TeslaMate describe un único coche: al vincular uno, se desvinculan los demás. */
function withTeslaMateLink(state: GarageState, changed: GarageVehicle): GarageState {
  if (!changed.teslaMateLinked) {
    return state
  }
  return {
    ...state,
    vehicles: state.vehicles.map((item) =>
      item.id === changed.id || !item.teslaMateLinked ? item : { ...item, teslaMateLinked: false },
    ),
  }
}

export function removeVehicle(state: GarageState, id: string): GarageState {
  if (state.vehicles.length <= 1 || !state.vehicles.some((item) => item.id === id)) {
    return state
  }
  const vehicles = state.vehicles.filter((item) => item.id !== id)
  return {
    ...state,
    vehicles,
    activeVehicleId: state.activeVehicleId === id ? vehicles[0].id : state.activeVehicleId,
    driver: state.driver?.referenceVehicleId === id ? null : state.driver,
  }
}

export function selectVehicle(state: GarageState, id: string): GarageState {
  return state.vehicles.some((item) => item.id === id) ? { ...state, activeVehicleId: id } : state
}

export function setDriverProfile(state: GarageState, driver: DriverProfile | null): GarageState {
  return { ...state, driver: driver ? normalizeDriver(driver, state.vehicles) : null }
}

export function setSoc(state: GarageState, socPercent: number): GarageState {
  return { ...state, socPercent: normalizeSoc(socPercent) }
}

export function setTerrain(state: GarageState, terrainFactorId: TerrainFactorId): GarageState {
  return { ...state, terrainFactorId: normalizeTerrain(terrainFactorId) }
}
