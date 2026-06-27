export type VehiclePresetId = string

export type VehiclePresetDefinition = {
  id: VehiclePresetId
  label: string
  brand: string
  model: string
  usableCapacityKwh: number
  referenceWhPerKm: number
}

export const DEFAULT_VEHICLE_PRESET_ID: VehiclePresetId = 'tesla-model3-sr-2023'

export const VEHICLE_PRESETS: VehiclePresetDefinition[] = [
  {
    id: 'tesla-model3-sr-2023',
    label: 'Tesla Model 3 SR (2023)',
    brand: 'Tesla',
    model: 'Model 3 Standard Range',
    usableCapacityKwh: 57,
    referenceWhPerKm: 142,
  },
  {
    id: 'tesla-model-y-lr',
    label: 'Tesla Model Y LR',
    brand: 'Tesla',
    model: 'Model Y Long Range',
    usableCapacityKwh: 75,
    referenceWhPerKm: 158,
  },
  {
    id: 'vw-id3-pro',
    label: 'VW ID.3 Pro',
    brand: 'Volkswagen',
    model: 'ID.3 Pro',
    usableCapacityKwh: 58,
    referenceWhPerKm: 155,
  },
  {
    id: 'hyundai-kona-64',
    label: 'Hyundai Kona Electric 64 kWh',
    brand: 'Hyundai',
    model: 'Kona Electric',
    usableCapacityKwh: 64,
    referenceWhPerKm: 168,
  },
  {
    id: 'renault-megane-etech',
    label: 'Renault Megane E-Tech',
    brand: 'Renault',
    model: 'Megane E-Tech Electric',
    usableCapacityKwh: 60,
    referenceWhPerKm: 162,
  },
  {
    id: 'bmw-i4-edrive40',
    label: 'BMW i4 eDrive40',
    brand: 'BMW',
    model: 'i4 eDrive40',
    usableCapacityKwh: 81,
    referenceWhPerKm: 175,
  },
  {
    id: 'mg4-standard',
    label: 'MG4 Standard',
    brand: 'MG',
    model: 'MG4 Electric',
    usableCapacityKwh: 51,
    referenceWhPerKm: 160,
  },
  {
    id: 'nissan-leaf-62',
    label: 'Nissan Leaf 62 kWh',
    brand: 'Nissan',
    model: 'Leaf e+',
    usableCapacityKwh: 59,
    referenceWhPerKm: 178,
  },
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

export function getTerrainFactor(terrainFactorId: TerrainFactorId): TerrainFactorDefinition {
  return TERRAIN_FACTORS.find((item) => item.id === terrainFactorId) ?? TERRAIN_FACTORS[0]
}
