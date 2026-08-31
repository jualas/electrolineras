import { describe, expect, it } from 'vitest'

import {
  ACTIVE_TRIP_STORAGE_KEY,
  ACTIVE_TRIP_TTL_MS,
  advanceTripProgress,
  clampTripProgress,
  loadActiveTripFromStorage,
  parseActiveTrip,
  persistActiveTripToStorage,
  type ActiveTripState,
} from './activeTrip'

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = { ...initial }
  return {
    get length() {
      return Object.keys(data).length
    },
    clear() {
      for (const key of Object.keys(data)) {
        delete data[key]
      }
    },
    getItem(key: string) {
      return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null
    },
    key(index: number) {
      return Object.keys(data)[index] ?? null
    },
    removeItem(key: string) {
      delete data[key]
    },
    setItem(key: string, value: string) {
      data[key] = value
    },
  }
}

const baseTrip: ActiveTripState = {
  version: 2,
  destination: { label: 'Cartagena', lat: 37.6, lon: -0.98 },
  waypoints: [
    { label: 'Tres Cantos', lat: 40.6, lon: -3.7 },
    { label: 'Cuenca', lat: 40.07, lon: -2.13 },
  ],
  lastPlan: {
    stopIds: ['st-1', 'st-2'],
    routeDistanceKm: 740,
    computedAt: 1_700_000_000_000,
  },
  progress: { completedStopOrders: [1], currentLegIndex: 1 },
  corridorKm: 12,
  routePreference: 'fastest',
  avoidTolls: true,
  chargingPreferences: { preferredOperators: ['Tesla'], maxPriceEurKwh: null },
  originMode: 'car',
  updatedAt: 1_700_000_000_000,
}

describe('parseActiveTrip v2', () => {
  it('restaura multi-vía y snapshot de plan', () => {
    const parsed = parseActiveTrip(JSON.stringify(baseTrip), baseTrip.updatedAt)
    expect(parsed).not.toBeNull()
    expect(parsed?.version).toBe(2)
    expect(parsed?.waypoints).toHaveLength(2)
    expect(parsed?.waypoints[0]?.label).toBe('Tres Cantos')
    expect(parsed?.lastPlan?.stopIds).toEqual(['st-1', 'st-2'])
    expect(parsed?.progress.currentLegIndex).toBe(1)
    expect(parsed?.routePreference).toBe('fastest')
  })

  it('migra payload v1 (solo destino) con defaults', () => {
    const v1 = {
      destination: { label: 'Irun', lat: 43.34, lon: -1.79 },
      corridorKm: 10,
      routePreference: 'shortest',
      chargingPreferences: { preferredOperators: [], maxPriceEurKwh: null },
      originMode: 'gps',
      updatedAt: baseTrip.updatedAt,
    }
    const parsed = parseActiveTrip(JSON.stringify(v1), baseTrip.updatedAt)
    expect(parsed?.destination.label).toBe('Irun')
    expect(parsed?.waypoints).toEqual([])
    expect(parsed?.lastPlan).toBeNull()
    expect(parsed?.progress).toEqual({ completedStopOrders: [], currentLegIndex: 0 })
    expect(parsed?.avoidTolls).toBe(true)
    expect(parsed?.version).toBe(2)
  })

  it('caduca tras TTL 48h', () => {
    const expiredAt = baseTrip.updatedAt + ACTIVE_TRIP_TTL_MS + 1
    expect(parseActiveTrip(JSON.stringify(baseTrip), expiredAt)).toBeNull()
  })
})

describe('localStorage migrate + persist', () => {
  it('migra sessionStorage → localStorage', () => {
    const local = memoryStorage()
    const session = memoryStorage({
      [ACTIVE_TRIP_STORAGE_KEY]: JSON.stringify(baseTrip),
    })
    const loaded = loadActiveTripFromStorage(local, session, baseTrip.updatedAt)
    expect(loaded?.waypoints).toHaveLength(2)
    expect(local.getItem(ACTIVE_TRIP_STORAGE_KEY)).toContain('Tres Cantos')
    expect(session.getItem(ACTIVE_TRIP_STORAGE_KEY)).toBeNull()
  })

  it('persiste y limpia session', () => {
    const local = memoryStorage()
    const session = memoryStorage({
      [ACTIVE_TRIP_STORAGE_KEY]: '{"stale":true}',
    })
    persistActiveTripToStorage(baseTrip, local, session)
    expect(JSON.parse(local.getItem(ACTIVE_TRIP_STORAGE_KEY) ?? '{}').waypoints).toHaveLength(2)
    expect(session.getItem(ACTIVE_TRIP_STORAGE_KEY)).toBeNull()
  })
})

describe('progreso de paradas', () => {
  it('advanceTripProgress incrementa currentLegIndex', () => {
    const next = advanceTripProgress(baseTrip, 1, 3)
    expect(next.progress.currentLegIndex).toBe(2)
    expect(next.progress.completedStopOrders).toContain(1)
  })

  it('clampTripProgress limita el índice al número de paradas', () => {
    const clamped = clampTripProgress({ completedStopOrders: [1, 2, 9], currentLegIndex: 5 }, 2)
    expect(clamped.currentLegIndex).toBe(1)
    expect(clamped.completedStopOrders).toEqual([1, 2])
  })
})
