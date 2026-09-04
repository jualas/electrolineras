import type { VehicleTelemetryResult } from '../api/types'
import { DEFAULT_RESERVE_SOC_PERCENT } from './vehicleProfile'
import { getVehiclePreset } from './vehiclePresets'

/**
 * TeslaMate reporta `rated_battery_range_km` a la autonomía actual (SOC actual), como el
 * modo «Rated» del cuadro — no normalizado al 100 %. Hay que dividir por el SOC actual para
 * obtener la autonomía nominal al 100 % que asumen el resto de cálculos (plan, alcance, etc.).
 * Así, si la batería pierde capacidad con el tiempo, la autonomía nominal baja con ella en vez
 * de quedarse fija en el valor de un preset estático.
 */
export function nominalRangeKm(telemetry: VehicleTelemetryResult): number | null {
  const rated = telemetry.rated_battery_range_km
  const soc = telemetry.usable_battery_level_pct ?? telemetry.battery_level_pct
  if (rated == null || rated <= 0 || soc == null || soc <= 0) {
    return null
  }
  return (rated * 100) / soc
}

/** Autonomía instantánea = nominal × SOC (TeslaMate «Autonomía nominal» × %). */
export function currentRangeFromNominal(telemetry: VehicleTelemetryResult): number | null {
  const nominal = nominalRangeKm(telemetry)
  const soc = telemetry.battery_level_pct
  if (nominal == null || soc <= 0) {
    return null
  }
  return (nominal * soc) / 100
}

export function planningRangeFromNominal(
  nominalKm: number,
  socPercent: number,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): number {
  if (nominalKm <= 0 || socPercent <= 0) {
    return 0
  }
  const usableSoc = Math.max(0, socPercent - reserveSocPercent)
  return Math.round((nominalKm * usableSoc) / 100)
}

export function chargingReachFromNominal(
  nominalKm: number,
  socPercent: number,
  minArrivalSoc = 5,
): number {
  if (nominalKm <= 0 || socPercent <= 0) {
    return 0
  }
  const usableSoc = Math.max(0, socPercent - minArrivalSoc)
  return Math.round((nominalKm * usableSoc) / 100)
}

export function formatTelemetrySummary(
  telemetry: VehicleTelemetryResult,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
): string | null {
  const nominal = nominalRangeKm(telemetry)
  const current = currentRangeFromNominal(telemetry)
  if (nominal == null || current == null) {
    return null
  }
  const soc = Math.round(telemetry.battery_level_pct)
  const planKm = planningRangeFromNominal(nominal, telemetry.battery_level_pct, reserveSocPercent)
  return `${soc} % SOC · ~${Math.round(current)} km · plan ~${planKm} km`
}

/** Solo sincroniza SOC al perfil global (otras pestañas). */
export function syncSocToVehicleProfile(
  telemetry: VehicleTelemetryResult,
  currentSocPercent: number,
  onSocChange: (socPercent: number) => void,
): boolean {
  const socPercent = Math.round(telemetry.battery_level_pct)
  if (socPercent === currentSocPercent) {
    return false
  }
  onSocChange(socPercent)
  return true
}

export function carOriginFromTelemetry(
  telemetry: VehicleTelemetryResult,
): { lat: number; lon: number; label: string; source: 'teslamate' } {
  const label = telemetry.display_name?.trim() || `Coche ${telemetry.car_id}`
  return {
    lat: telemetry.lat,
    lon: telemetry.lon,
    label,
    source: 'teslamate',
  }
}

/** Perfil de energía alineado con api.integrations.telemetry_energy.vehicle_energy_from_telemetry */
export function telemetryToChargingPlanQuery(
  telemetry: VehicleTelemetryResult,
  terrainFactor: number,
  reserveSocPercent = DEFAULT_RESERVE_SOC_PERCENT,
  departureSocPercent?: number | null,
  vehiclePresetId?: string,
): {
  soc_percent: number
  usable_capacity_kwh: number
  consumption_wh_per_km: number
  terrain_factor: number
  reserve_soc_percent: number
  vehicle_preset_id: string
} {
  const nominal = nominalRangeKm(telemetry)
  if (nominal == null || nominal <= 0) {
    throw new Error('TeslaMate sin autonomía nominal (rated_battery_range_km)')
  }
  const liveSoc = telemetry.battery_level_pct
  const soc =
    departureSocPercent == null
      ? liveSoc
      : Math.min(100, Math.max(5, departureSocPercent))
  const terrain = Math.max(0.01, Math.min(2, terrainFactor))
  const preset = getVehiclePreset(vehiclePresetId ?? 'tesla-model3-sr-2023')
  const usableCapacityKwh = preset.usableCapacityKwh
  // Preferir efficiency TeslaMate; si no, reference del preset (afinado a ~137–140 Wh/km).
  const efficiencyWh =
    telemetry.efficiency_kwh_per_km != null && telemetry.efficiency_kwh_per_km > 0
      ? telemetry.efficiency_kwh_per_km * 1000
      : preset.referenceWhPerKm
  const consumptionWhPerKm = efficiencyWh * terrain
  return {
    soc_percent: soc,
    usable_capacity_kwh: usableCapacityKwh,
    consumption_wh_per_km: consumptionWhPerKm,
    terrain_factor: terrain,
    reserve_soc_percent: reserveSocPercent,
    vehicle_preset_id: preset.id,
  }
}
