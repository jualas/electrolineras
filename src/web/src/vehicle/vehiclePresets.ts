export type VehiclePresetId = string

export type VehiclePresetDefinition = {
  id: VehiclePresetId
  label: string
  brand: string
  model: string
  usableCapacityKwh: number
  /** Autonomía de referencia al 100 % SOC (como el cuadro del coche / WLTP). */
  ratedRangeKm: number
  /** Pico DC del preset (alineado con api.routing.dc_charge_curve). */
  peakDcKw: number
  /** Consumo calibrado: capacidad útil ÷ autonomía nominal. */
  referenceWhPerKm: number
}

export const DEFAULT_VEHICLE_PRESET_ID: VehiclePresetId = 'tesla-model3-sr-2023'

function preset(
  id: VehiclePresetId,
  label: string,
  brand: string,
  model: string,
  usableCapacityKwh: number,
  ratedRangeKm: number,
  peakDcKw: number,
): VehiclePresetDefinition {
  return {
    id,
    label,
    brand,
    model,
    usableCapacityKwh,
    ratedRangeKm,
    peakDcKw,
    referenceWhPerKm: Math.round((usableCapacityKwh * 1000) / ratedRangeKm),
  }
}

export const VEHICLE_PRESETS: VehiclePresetDefinition[] = [
  preset('tesla-model3-sr-2023', 'Tesla Model 3 SR (2023)', 'Tesla', 'Model 3 Standard Range', 57, 420, 170),
  preset('tesla-model-y-lr', 'Tesla Model Y LR', 'Tesla', 'Model Y Long Range', 75, 533, 250),
  preset('vw-id3-pro', 'VW ID.3 Pro', 'Volkswagen', 'ID.3 Pro', 58, 426, 125),
  preset('hyundai-kona-64', 'Hyundai Kona Electric 64 kWh', 'Hyundai', 'Kona Electric', 64, 484, 100),
  preset('renault-megane-etech', 'Renault Megane E-Tech', 'Renault', 'Megane E-Tech Electric', 60, 450, 130),
  preset('bmw-i4-edrive40', 'BMW i4 eDrive40', 'BMW', 'i4 eDrive40', 81, 590, 205),
  preset('mg4-standard', 'MG4 Standard', 'MG', 'MG4 Electric', 51, 435, 135),
  preset('nissan-leaf-62', 'Nissan Leaf 62 kWh', 'Nissan', 'Leaf e+', 59, 385, 100),
]

export type TerrainFactorId = 'flat' | 'rolling' | 'mountain'

export type TerrainFactorDefinition = {
  id: TerrainFactorId
  label: string
  factor: number
  hint: string
}

export const TERRAIN_FACTORS: TerrainFactorDefinition[] = [
  { id: 'flat', label: 'Llano', factor: 1, hint: 'Autopista / llano' },
  { id: 'rolling', label: 'Ondulado', factor: 1.15, hint: '+15 % consumo' },
  { id: 'mountain', label: 'Sierra', factor: 1.25, hint: '+25 % consumo' },
]

export const DEFAULT_TERRAIN_FACTOR_ID: TerrainFactorId = 'flat'

export function getVehiclePreset(presetId: VehiclePresetId): VehiclePresetDefinition {
  return VEHICLE_PRESETS.find((item) => item.id === presetId) ?? VEHICLE_PRESETS[0]
}

export function peakDcKwForPreset(presetId: VehiclePresetId | undefined): number {
  return getVehiclePreset(presetId ?? DEFAULT_VEHICLE_PRESET_ID).peakDcKw
}

export function getTerrainFactor(terrainFactorId: TerrainFactorId): TerrainFactorDefinition {
  return TERRAIN_FACTORS.find((item) => item.id === terrainFactorId) ?? TERRAIN_FACTORS[0]
}
