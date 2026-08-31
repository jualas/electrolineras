export const CONSUMPTION_DIVERGENCE_THRESHOLD_PCT = 15

export function effectiveConsumptionWhPerKm(query: {
  consumption_wh_per_km: number
  terrain_factor?: number
}): number {
  const terrain = query.terrain_factor ?? 1
  return query.consumption_wh_per_km * terrain
}

export function consumptionDivergencePct(baselineWhPerKm: number, currentWhPerKm: number): number {
  if (baselineWhPerKm <= 0 || currentWhPerKm <= 0) {
    return 0
  }
  return (Math.abs(currentWhPerKm - baselineWhPerKm) / baselineWhPerKm) * 100
}

export function isConsumptionDivergent(
  baselineWhPerKm: number,
  currentWhPerKm: number,
  thresholdPct = CONSUMPTION_DIVERGENCE_THRESHOLD_PCT,
): boolean {
  return consumptionDivergencePct(baselineWhPerKm, currentWhPerKm) > thresholdPct
}
