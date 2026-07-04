import type { RoutePreference } from '../api/types'
import type { ChargingPreferencesState } from './chargingPreferences'

export type ActiveTripDestination = {
  label: string
  lat: number
  lon: number
}

export type ActiveTripState = {
  destination: ActiveTripDestination
  corridorKm: number
  routePreference: RoutePreference
  avoidTolls: boolean
  chargingPreferences: ChargingPreferencesState
  originMode: 'car' | 'gps' | 'simulation'
  updatedAt: number
}

export type EnMarchaSettings = {
  autoFollow: boolean
}

export const ACTIVE_TRIP_STORAGE_KEY = 'electrolineras.activeTrip'
export const EN_MARCHA_SETTINGS_STORAGE_KEY = 'electrolineras.enMarchaSettings'

export const DEFAULT_EN_MARCHA_SETTINGS: EnMarchaSettings = {
  autoFollow: true,
}

export function parseActiveTrip(raw: string | null): ActiveTripState | null {
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ActiveTripState>
    const destination = parsed.destination
    if (
      !destination ||
      typeof destination.label !== 'string' ||
      typeof destination.lat !== 'number' ||
      typeof destination.lon !== 'number'
    ) {
      return null
    }
    return {
      destination: {
        label: destination.label,
        lat: destination.lat,
        lon: destination.lon,
      },
      corridorKm: typeof parsed.corridorKm === 'number' ? parsed.corridorKm : 10,
      routePreference:
        parsed.routePreference === 'fastest' ||
        parsed.routePreference === 'shortest' ||
        parsed.routePreference === 'conventional'
          ? parsed.routePreference
          : 'shortest',
      avoidTolls: Boolean(parsed.avoidTolls),
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
      updatedAt: typeof parsed.updatedAt === 'number' ? parsed.updatedAt : Date.now(),
    }
  } catch {
    return null
  }
}

export function parseEnMarchaSettings(raw: string | null): EnMarchaSettings {
  if (!raw) {
    return DEFAULT_EN_MARCHA_SETTINGS
  }
  try {
    const parsed = JSON.parse(raw) as Partial<EnMarchaSettings>
    return {
      autoFollow: parsed.autoFollow !== false,
    }
  } catch {
    return DEFAULT_EN_MARCHA_SETTINGS
  }
}
