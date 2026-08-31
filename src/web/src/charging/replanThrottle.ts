import { haversineKm } from './planRouteStops'

export const AUTO_REPLAN_MIN_MOVE_KM = 2
export const AUTO_REPLAN_MIN_INTERVAL_MS = 5 * 60_000
export const AUTO_REPLAN_SOC_DELTA_PP = 3

export type AutoReplanSnapshot = {
  at: number
  lat: number
  lon: number
  soc: number
}

export function stripOriginFromSearchKey(searchKey: string): string | null {
  try {
    const parsed = JSON.parse(searchKey) as { origin?: unknown }
    if (!parsed || typeof parsed !== 'object') {
      return null
    }
    const { origin: _origin, ...rest } = parsed
    return JSON.stringify(rest)
  } catch {
    return null
  }
}

export function isOriginOnlySearchKeyChange(previousKey: string | null, nextKey: string): boolean {
  if (!previousKey) {
    return false
  }
  const prevRest = stripOriginFromSearchKey(previousKey)
  const nextRest = stripOriginFromSearchKey(nextKey)
  return prevRest != null && nextRest != null && prevRest === nextRest
}

export function shouldThrottleAutoReplan(options: {
  last: AutoReplanSnapshot | null
  now?: number
  origin: { lat: number; lon: number }
  soc: number
  minMoveKm?: number
  minIntervalMs?: number
  socDeltaPp?: number
}): boolean {
  const {
    last,
    now = Date.now(),
    origin,
    soc,
    minMoveKm = AUTO_REPLAN_MIN_MOVE_KM,
    minIntervalMs = AUTO_REPLAN_MIN_INTERVAL_MS,
    socDeltaPp = AUTO_REPLAN_SOC_DELTA_PP,
  } = options
  if (!last) {
    return false
  }
  const movedKm = haversineKm(last, origin)
  const elapsedMs = now - last.at
  const socDelta = Math.abs(soc - last.soc)
  if (socDelta >= socDeltaPp) {
    return false
  }
  if (movedKm >= minMoveKm) {
    return false
  }
  if (elapsedMs >= minIntervalMs) {
    return false
  }
  return true
}
