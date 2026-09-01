import type { RoutePreference } from '../api/types'
import type { ChargingPreferencesState } from './chargingPreferences'

export type ActiveTripDestination = {
  label: string
  lat: number
  lon: number
}

/** Vías del usuario (A→…→A), no paradas DC del planificador. */
export type ActiveTripWaypoint = ActiveTripDestination

export type ActiveTripLastPlan = {
  stopIds: string[]
  routeDistanceKm: number | null
  computedAt: number
  /** Wh/km efectivo (× terrain) usado al calcular el plan. */
  consumptionWhPerKmEffective?: number | null
}

export type ReplanReason = 'manual' | 'auto_follow' | 'stop_completed'

export type ActiveTripReplanTelemetry = {
  count: number
  lastAt: number | null
  lastReason: ReplanReason | null
}

export const EMPTY_REPLAN_TELEMETRY: ActiveTripReplanTelemetry = {
  count: 0,
  lastAt: null,
  lastReason: null,
}

export type ActiveTripProgress = {
  completedStopOrders: number[]
  currentLegIndex: number
}

export type ActiveTripState = {
  /** v2: waypoints + lastPlan + progress + TTL localStorage */
  version: 2
  destination: ActiveTripDestination
  waypoints: ActiveTripWaypoint[]
  lastPlan: ActiveTripLastPlan | null
  progress: ActiveTripProgress
  replan: ActiveTripReplanTelemetry
  corridorKm: number
  routePreference: RoutePreference
  avoidTolls: boolean
  chargingPreferences: ChargingPreferencesState
  originMode: 'car' | 'gps' | 'simulation'
  updatedAt: number
}

export type EnMarchaSettings = {
  autoFollow: boolean
  /** Seguimiento GPS del móvil durante viaje activo (#6144). */
  gpsEnabled: boolean
  /** Centrar mapa en la posición del usuario (#6145); independiente de autoFollow. */
  centerOnMe: boolean
}

export const ACTIVE_TRIP_STORAGE_KEY = 'electrolineras.activeTrip'
export const EN_MARCHA_SETTINGS_STORAGE_KEY = 'electrolineras.enMarchaSettings'
/** TTL viaje activo en localStorage (48 h). */
export const ACTIVE_TRIP_TTL_MS = 48 * 60 * 60 * 1000

export const DEFAULT_EN_MARCHA_SETTINGS: EnMarchaSettings = {
  autoFollow: true,
  gpsEnabled: true,
  centerOnMe: true,
}

export const EMPTY_ACTIVE_TRIP_PROGRESS: ActiveTripProgress = {
  completedStopOrders: [],
  currentLegIndex: 0,
}

function isFiniteCoord(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function parseWaypoint(raw: unknown): ActiveTripWaypoint | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const point = raw as Partial<ActiveTripWaypoint>
  if (
    typeof point.label !== 'string' ||
    !point.label.trim() ||
    !isFiniteCoord(point.lat) ||
    !isFiniteCoord(point.lon)
  ) {
    return null
  }
  return { label: point.label.trim(), lat: point.lat, lon: point.lon }
}

function parseLastPlan(raw: unknown): ActiveTripLastPlan | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const plan = raw as Partial<ActiveTripLastPlan>
  if (!Array.isArray(plan.stopIds)) {
    return null
  }
  return {
    stopIds: plan.stopIds.filter((id): id is string => typeof id === 'string' && id.length > 0),
    routeDistanceKm:
      typeof plan.routeDistanceKm === 'number' && Number.isFinite(plan.routeDistanceKm)
        ? plan.routeDistanceKm
        : null,
    computedAt: typeof plan.computedAt === 'number' ? plan.computedAt : Date.now(),
    consumptionWhPerKmEffective:
      typeof plan.consumptionWhPerKmEffective === 'number' &&
      Number.isFinite(plan.consumptionWhPerKmEffective)
        ? plan.consumptionWhPerKmEffective
        : null,
  }
}

function parseReplanTelemetry(raw: unknown): ActiveTripReplanTelemetry {
  if (!raw || typeof raw !== 'object') {
    return { ...EMPTY_REPLAN_TELEMETRY }
  }
  const telemetry = raw as Partial<ActiveTripReplanTelemetry>
  const reason =
    telemetry.lastReason === 'manual' ||
    telemetry.lastReason === 'auto_follow' ||
    telemetry.lastReason === 'stop_completed'
      ? telemetry.lastReason
      : null
  return {
    count:
      typeof telemetry.count === 'number' && telemetry.count >= 0
        ? Math.floor(telemetry.count)
        : 0,
    lastAt: typeof telemetry.lastAt === 'number' ? telemetry.lastAt : null,
    lastReason: reason,
  }
}

export function bumpReplanTelemetry(
  telemetry: ActiveTripReplanTelemetry | undefined,
  reason: ReplanReason,
  now: number = Date.now(),
): ActiveTripReplanTelemetry {
  const base = telemetry ?? EMPTY_REPLAN_TELEMETRY
  return {
    count: base.count + 1,
    lastAt: now,
    lastReason: reason,
  }
}

function parseProgress(raw: unknown): ActiveTripProgress {
  if (!raw || typeof raw !== 'object') {
    return { ...EMPTY_ACTIVE_TRIP_PROGRESS }
  }
  const progress = raw as Partial<ActiveTripProgress>
  const completed = Array.isArray(progress.completedStopOrders)
    ? progress.completedStopOrders.filter(
        (order): order is number => typeof order === 'number' && Number.isFinite(order),
      )
    : []
  const currentLegIndex =
    typeof progress.currentLegIndex === 'number' && progress.currentLegIndex >= 0
      ? Math.floor(progress.currentLegIndex)
      : 0
  return { completedStopOrders: completed, currentLegIndex }
}

/** Avanza el progreso tras completar una parada DC planificada. */
export function advanceTripProgress(
  trip: ActiveTripState,
  stopOrder: number,
  totalStops: number,
): ActiveTripState {
  const completed = trip.progress.completedStopOrders.includes(stopOrder)
    ? trip.progress.completedStopOrders
    : [...trip.progress.completedStopOrders, stopOrder]
  const nextIndex = Math.min(trip.progress.currentLegIndex + 1, Math.max(0, totalStops))
  return {
    ...trip,
    progress: {
      completedStopOrders: completed,
      currentLegIndex: nextIndex,
    },
    updatedAt: Date.now(),
  }
}

/** Mantiene el índice de parada al replanificar (p. ej. tras desvío). */
export function clampTripProgress(
  progress: ActiveTripProgress,
  stopCount: number,
): ActiveTripProgress {
  if (stopCount <= 0) {
    return { ...EMPTY_ACTIVE_TRIP_PROGRESS }
  }
  const maxIndex = stopCount - 1
  return {
    completedStopOrders: progress.completedStopOrders.filter((order) => order >= 1 && order <= stopCount),
    currentLegIndex: Math.min(Math.max(0, progress.currentLegIndex), maxIndex),
  }
}

export function isActiveTripExpired(trip: ActiveTripState, now: number = Date.now()): boolean {
  return now - trip.updatedAt > ACTIVE_TRIP_TTL_MS
}

export function parseActiveTrip(raw: string | null, now: number = Date.now()): ActiveTripState | null {
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ActiveTripState> & {
      destination?: Partial<ActiveTripDestination>
    }
    const destination = parseWaypoint(parsed.destination)
    if (!destination) {
      return null
    }

    const updatedAt = typeof parsed.updatedAt === 'number' ? parsed.updatedAt : now
    const draft: ActiveTripState = {
      version: 2,
      destination,
      waypoints: Array.isArray(parsed.waypoints)
        ? parsed.waypoints.map(parseWaypoint).filter((point): point is ActiveTripWaypoint => point != null)
        : [],
      lastPlan: parseLastPlan(parsed.lastPlan),
      progress: parseProgress(parsed.progress),
      replan: parseReplanTelemetry(parsed.replan),
      corridorKm: typeof parsed.corridorKm === 'number' ? parsed.corridorKm : 10,
      routePreference:
        parsed.routePreference === 'fastest' ||
        parsed.routePreference === 'shortest' ||
        parsed.routePreference === 'conventional'
          ? parsed.routePreference
          : 'shortest',
      avoidTolls:
        typeof parsed.avoidTolls === 'boolean' ? parsed.avoidTolls : true,
      chargingPreferences:
        parsed.chargingPreferences && typeof parsed.chargingPreferences === 'object'
          ? {
              preferredOperators: Array.isArray(parsed.chargingPreferences.preferredOperators)
                ? parsed.chargingPreferences.preferredOperators.filter(
                    (item): item is string => typeof item === 'string',
                  )
                : [],
              maxPriceEurKwh:
                typeof parsed.chargingPreferences.maxPriceEurKwh === 'number'
                  ? parsed.chargingPreferences.maxPriceEurKwh
                  : null,
            }
          : { preferredOperators: [], maxPriceEurKwh: null },
      originMode:
        parsed.originMode === 'car' || parsed.originMode === 'gps' || parsed.originMode === 'simulation'
          ? parsed.originMode
          : 'gps',
      updatedAt,
    }

    if (isActiveTripExpired(draft, now)) {
      return null
    }
    return draft
  } catch {
    return null
  }
}

/**
 * Lee viaje activo: localStorage (v2) con migración desde sessionStorage (v1).
 * Si migra o caduca, limpia la clave antigua de session.
 */
export function loadActiveTripFromStorage(
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null = typeof window !== 'undefined'
    ? window.localStorage
    : null,
  session: Pick<Storage, 'getItem' | 'removeItem'> | null = typeof window !== 'undefined'
    ? window.sessionStorage
    : null,
  now: number = Date.now(),
): ActiveTripState | null {
  const fromLocal = storage ? parseActiveTrip(storage.getItem(ACTIVE_TRIP_STORAGE_KEY), now) : null
  if (fromLocal) {
    session?.removeItem(ACTIVE_TRIP_STORAGE_KEY)
    return fromLocal
  }

  const fromSession = session ? parseActiveTrip(session.getItem(ACTIVE_TRIP_STORAGE_KEY), now) : null
  if (fromSession && storage) {
    storage.setItem(ACTIVE_TRIP_STORAGE_KEY, JSON.stringify(fromSession))
    session?.removeItem(ACTIVE_TRIP_STORAGE_KEY)
    return fromSession
  }

  storage?.removeItem(ACTIVE_TRIP_STORAGE_KEY)
  session?.removeItem(ACTIVE_TRIP_STORAGE_KEY)
  return null
}

export function persistActiveTripToStorage(
  trip: ActiveTripState | null,
  storage: Pick<Storage, 'setItem' | 'removeItem'> | null = typeof window !== 'undefined'
    ? window.localStorage
    : null,
  session: Pick<Storage, 'removeItem'> | null = typeof window !== 'undefined'
    ? window.sessionStorage
    : null,
): void {
  session?.removeItem(ACTIVE_TRIP_STORAGE_KEY)
  if (!storage) {
    return
  }
  if (!trip) {
    storage.removeItem(ACTIVE_TRIP_STORAGE_KEY)
    return
  }
  storage.setItem(ACTIVE_TRIP_STORAGE_KEY, JSON.stringify({ ...trip, version: 2 }))
}

export function parseEnMarchaSettings(raw: string | null): EnMarchaSettings {
  if (!raw) {
    return DEFAULT_EN_MARCHA_SETTINGS
  }
  try {
    const parsed = JSON.parse(raw) as Partial<EnMarchaSettings>
    return {
      autoFollow: parsed.autoFollow !== false,
      gpsEnabled: parsed.gpsEnabled !== false,
      centerOnMe: parsed.centerOnMe !== false,
    }
  } catch {
    return DEFAULT_EN_MARCHA_SETTINGS
  }
}

export function loadEnMarchaSettingsFromStorage(
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null = typeof window !== 'undefined'
    ? window.localStorage
    : null,
  session: Pick<Storage, 'getItem' | 'removeItem'> | null = typeof window !== 'undefined'
    ? window.sessionStorage
    : null,
): EnMarchaSettings {
  const localRaw = storage?.getItem(EN_MARCHA_SETTINGS_STORAGE_KEY) ?? null
  if (localRaw) {
    session?.removeItem(EN_MARCHA_SETTINGS_STORAGE_KEY)
    return parseEnMarchaSettings(localRaw)
  }
  const sessionRaw = session?.getItem(EN_MARCHA_SETTINGS_STORAGE_KEY) ?? null
  const settings = parseEnMarchaSettings(sessionRaw)
  if (sessionRaw && storage) {
    storage.setItem(EN_MARCHA_SETTINGS_STORAGE_KEY, JSON.stringify(settings))
    session?.removeItem(EN_MARCHA_SETTINGS_STORAGE_KEY)
  }
  return settings
}
