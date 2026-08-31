import { describe, expect, it } from 'vitest'

import { buildPlanSearchKey } from './planSearchKey'
import { DEFAULT_CHARGING_PREFERENCES } from './chargingPreferences'
import {
  isOriginOnlySearchKeyChange,
  shouldThrottleAutoReplan,
} from './replanThrottle'

const vehicleQuery = {
  soc_percent: 70,
  usable_capacity_kwh: 60,
  consumption_wh_per_km: 160,
  terrain_factor: 1,
}

describe('replanThrottle', () => {
  it('detecta cambio solo de origen en searchKey', () => {
    const base = buildPlanSearchKey({
      originMode: 'gps',
      origin: { lat: 37.6, lon: -0.99 },
      dest: { label: 'Cartagena', lat: 37.6, lon: -0.98 },
      vehicleQuery,
      corridorKm: 10,
      emergencyMode: false,
      routePreference: 'fastest',
      avoidTolls: true,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
    })
    const moved = buildPlanSearchKey({
      originMode: 'gps',
      origin: { lat: 37.61, lon: -0.98 },
      dest: { label: 'Cartagena', lat: 37.6, lon: -0.98 },
      vehicleQuery,
      corridorKm: 10,
      emergencyMode: false,
      routePreference: 'fastest',
      avoidTolls: true,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
    })
    expect(isOriginOnlySearchKeyChange(base, moved)).toBe(true)
  })

  it('no limita replan si el movimiento supera 2 km', () => {
    const throttled = shouldThrottleAutoReplan({
      last: { at: Date.now(), lat: 37.6, lon: -0.99, soc: 70 },
      origin: { lat: 37.8, lon: -1.2 },
      soc: 70,
    })
    expect(throttled).toBe(false)
  })

  it('limita replan por tiempo y distancia corta', () => {
    const throttled = shouldThrottleAutoReplan({
      last: { at: Date.now() - 60_000, lat: 37.6, lon: -0.99, soc: 70 },
      origin: { lat: 37.601, lon: -0.991 },
      soc: 70,
    })
    expect(throttled).toBe(true)
  })
})
